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
_AUTHORITY_RANK = {"A0": 0, "A0_READ": 0, "A1": 1, "A1_INTERNAL": 1, "A2": 2, "A3": 3}
_OPEN_WORKSTREAM_STATES = {"OPEN", "DRAFT", "RUNNING", "READY"}
_SCORE_WEIGHTS = {"quality": 0.16, "reliability": 0.22, "freshness": 0.15, "proof_strength": 0.20, "latency": 0.06, "cost": 0.05, "owner_burden": 0.06, "risk": 0.10}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
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


def _clean_paths(values: Iterable[str]) -> tuple[str, ...]:
    cleaned: set[str] = set()
    for raw in values:
        value = str(raw).strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if not value or value.startswith("/") or any(part in {"", ".."} for part in value.split("/")):
            raise ValueError("repository paths must be relative and traversal-free")
        cleaned.add(value.rstrip("/"))
    if not cleaned:
        raise ValueError("at least one repository path is required")
    return tuple(sorted(cleaned))


def _path_overlap(left: str, right: str) -> bool:
    left, right = left.rstrip("/"), right.rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def overlapping_paths(left: Iterable[str], right: Iterable[str]) -> tuple[str, ...]:
    lhs, rhs = _clean_paths(left), _clean_paths(right)
    return tuple(sorted({a for a in lhs for b in rhs if _path_overlap(a, b)}))


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
    REPAIR = "REPAIR"
    RECONCILE = "RECONCILE"


class ProofState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    AUTHORISED = "AUTHORISED"
    EXECUTED = "EXECUTED"
    READBACK_VERIFIED = "READBACK_VERIFIED"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"


@dataclass(frozen=True)
class MissionLease:
    mission_id: str
    lane_id: str
    holder_id: str
    base_main_sha: str
    lease_epoch: int
    path_scope: tuple[str, ...]
    issued_at: str
    expires_at: str
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False
    fence_token: str = ""

    @classmethod
    def create(cls, *, mission_id: str, lane_id: str, holder_id: str, base_main_sha: str, lease_epoch: int, path_scope: Iterable[str], issued_at: str, expires_at: str, authority_ceiling: str = "A1_INTERNAL", external_effect: bool = False) -> "MissionLease":
        _validate_id(mission_id, "mission_id"); _validate_id(lane_id, "lane_id"); _validate_id(holder_id, "holder_id"); _validate_sha(base_main_sha, "base_main_sha")
        if not isinstance(lease_epoch, int) or lease_epoch < 1: raise ValueError("lease_epoch must be positive")
        if _AUTHORITY_RANK.get(authority_ceiling, 99) > _AUTHORITY_RANK["A1_INTERNAL"] or external_effect: raise ValueError("mission lease cannot create provider/external authority")
        issued, expires = _parse_time(issued_at), _parse_time(expires_at)
        if expires <= issued: raise ValueError("lease expiry must be after issuance")
        scope = _clean_paths(path_scope)
        body = {"mission_id": mission_id, "lane_id": lane_id, "holder_id": holder_id, "base_main_sha": base_main_sha, "lease_epoch": lease_epoch, "path_scope": scope, "issued_at": issued.isoformat(), "expires_at": expires.isoformat(), "authority_ceiling": authority_ceiling, "external_effect": False}
        return cls(fence_token=f"FMACF-FENCE-{_digest(body)[:32].upper()}", **body)

    def active_at(self, now: str) -> bool:
        instant = _parse_time(now); return _parse_time(self.issued_at) <= instant < _parse_time(self.expires_at)

    def refresh(self, *, new_main_sha: str, new_epoch: int, issued_at: str, expires_at: str) -> "MissionLease":
        if new_epoch <= self.lease_epoch: raise ValueError("new lease epoch must increase")
        return MissionLease.create(mission_id=self.mission_id, lane_id=self.lane_id, holder_id=self.holder_id, base_main_sha=new_main_sha, lease_epoch=new_epoch, path_scope=self.path_scope, issued_at=issued_at, expires_at=expires_at, authority_ceiling=self.authority_ceiling)


@dataclass(frozen=True)
class WorkstreamObservation:
    workstream_id: str; base_sha: str; head_sha: str; paths: tuple[str, ...]; state: str = "OPEN"
    @classmethod
    def create(cls, *, workstream_id: str, base_sha: str, head_sha: str, paths: Iterable[str], state: str = "OPEN") -> "WorkstreamObservation":
        _validate_id(workstream_id, "workstream_id")
        return cls(workstream_id=workstream_id, base_sha=_validate_sha(base_sha, "base_sha"), head_sha=_validate_sha(head_sha, "head_sha"), paths=_clean_paths(paths), state=str(state).upper())


@dataclass(frozen=True)
class ConcurrencyDecision:
    state: ConcurrencyState; write_allowed: bool; current_main_sha: str; lease_main_sha: str; overlapping_workstreams: tuple[str, ...]; overlapping_paths: tuple[str, ...]; next_action: str


class ConcurrencyGuard:
    def evaluate(self, *, lease: MissionLease, current_main_sha: str, now: str, main_changed_paths: Iterable[str] = (), active_workstreams: Sequence[WorkstreamObservation] = ()) -> ConcurrencyDecision:
        _validate_sha(current_main_sha, "current_main_sha")
        if not lease.active_at(now): return ConcurrencyDecision(ConcurrencyState.LEASE_EXPIRED, False, current_main_sha, lease.base_main_sha, (), (), "RENEW_LEASE_FROM_FRESH_MAIN")
        streams: set[str] = set(); hits: set[str] = set()
        for work in active_workstreams:
            if work.state not in _OPEN_WORKSTREAM_STATES: continue
            overlap = overlapping_paths(lease.path_scope, work.paths)
            if overlap: streams.add(work.workstream_id); hits.update(overlap)
        if streams: return ConcurrencyDecision(ConcurrencyState.ACTIVE_WORKSTREAM_OVERLAP_HOLD, False, current_main_sha, lease.base_main_sha, tuple(sorted(streams)), tuple(sorted(hits)), "RECONCILE_OR_SERIALIZE_OVERLAPPING_WORKSTREAMS")
        if current_main_sha != lease.base_main_sha:
            changed = tuple(str(x) for x in main_changed_paths if str(x).strip()); overlap = overlapping_paths(lease.path_scope, changed) if changed else ()
            if overlap: return ConcurrencyDecision(ConcurrencyState.MAIN_DRIFT_OVERLAP_HOLD, False, current_main_sha, lease.base_main_sha, (), overlap, "RECONCILE_CHANGED_PATHS_AND_REISSUE_LEASE")
            return ConcurrencyDecision(ConcurrencyState.MAIN_DRIFT_FAST_RECONVERGE, False, current_main_sha, lease.base_main_sha, (), (), "FAST_RECONVERGE_ON_CURRENT_MAIN_AND_REISSUE_LEASE")
        return ConcurrencyDecision(ConcurrencyState.CLEAR, True, current_main_sha, lease.base_main_sha, (), (), "WRITE_WITH_FENCE_TOKEN_AND_POST_WRITE_READBACK")


@dataclass(frozen=True)
class PreWriteFenceReceipt:
    mission_id: str; lease_epoch: int; base_main_sha: str; current_main_sha: str; fence_token: str; path_digest: str; allowed: bool; reason: str; receipt_digest: str


class PreWriteFence:
    def authorise(self, *, lease: MissionLease, decision: ConcurrencyDecision, current_main_sha: str | None = None, intended_paths: Iterable[str]) -> PreWriteFenceReceipt:
        paths = _clean_paths(intended_paths); current = current_main_sha or decision.current_main_sha; _validate_sha(current, "current_main_sha")
        if any(not any(_path_overlap(path, scope) for scope in lease.path_scope) for path in paths): allowed, reason = False, "INTENDED_PATH_OUTSIDE_LEASE_SCOPE"
        elif not decision.write_allowed: allowed, reason = False, decision.state.value
        elif current != lease.base_main_sha: allowed, reason = False, "STALE_MAIN_FENCE"
        else: allowed, reason = True, "PREWRITE_FENCE_VERIFIED"
        body = {"mission_id": lease.mission_id, "lease_epoch": lease.lease_epoch, "base_main_sha": lease.base_main_sha, "current_main_sha": current, "fence_token": lease.fence_token, "path_digest": _digest(paths), "allowed": allowed, "reason": reason}
        return PreWriteFenceReceipt(receipt_digest=_digest(body), **body)


@dataclass(frozen=True)
class FailureMemoryRecord:
    fingerprint: str; route_id: str; status: FailureStatus | str; failure_proof_ref: str; retry_condition: str; recovery_proof_ref: str = ""
    def normalized_status(self) -> FailureStatus:
        try: return FailureStatus(str(self.status))
        except ValueError as exc: raise ValueError("unknown failure status") from exc
    def validate(self) -> "FailureMemoryRecord":
        if len(self.fingerprint.strip()) < 6: raise ValueError("failure fingerprint is too short")
        _validate_id(self.route_id, "route_id")
        if not self.failure_proof_ref.strip() or not self.retry_condition.strip(): raise ValueError("failure record requires proof and retry condition")
        if self.normalized_status() == FailureStatus.CLOSED and not self.recovery_proof_ref.strip(): raise ValueError("closed failure requires recovery proof")
        return self
    def blockers_for(self, route_id: str, retry_evidence_refs: Iterable[str]) -> tuple[str, ...]:
        self.validate()
        if route_id != self.route_id: return ()
        refs = set(retry_evidence_refs); state = self.normalized_status()
        if state == FailureStatus.OPEN: return (f"KNOWN_OPEN_FAILURE:{self.fingerprint}",)
        if state in {FailureStatus.MITIGATED, FailureStatus.CLOSED} and self.recovery_proof_ref not in refs: return (f"RECOVERY_PROOF_NOT_BOUND:{self.fingerprint}",)
        return ()


class FailureMemoryGate:
    def blockers(self, *, route_id: str, memories: Sequence[FailureMemoryRecord], retry_evidence_refs: Iterable[str] = ()) -> tuple[str, ...]:
        out: list[str] = []
        for memory in memories: out.extend(memory.blockers_for(route_id, retry_evidence_refs))
        return tuple(sorted(set(out)))


@dataclass(frozen=True)
class CapabilityRoute:
    route_id: str; capability_id: str; reality_state: str; required_reality_state: str = "C3"; readiness: str = "READY"; authority_required: str = "A1_INTERNAL"; proof_ref: str = ""; external_effect: bool = False; retry_evidence_refs: tuple[str, ...] = (); quality: float = 0.5; reliability: float = 0.5; freshness: float = 0.5; proof_strength: float = 0.5; latency: float = 0.5; cost: float = 0.5; owner_burden: float = 0.5; risk: float = 0.5; fitness: float | None = None
    def validate(self) -> "CapabilityRoute":
        _validate_id(self.route_id, "route_id"); _validate_id(self.capability_id, "capability_id")
        if self.reality_state not in _REALITY_RANK or self.required_reality_state not in _REALITY_RANK: raise ValueError("unknown capability reality state")
        if self.readiness not in {"READY", "HOLD", "BLOCKED", "STALE"}: raise ValueError("unknown readiness")
        if self.authority_required not in _AUTHORITY_RANK: raise ValueError("unknown authority requirement")
        if not self.proof_ref.strip(): raise ValueError("route requires a proof reference")
        for name in _SCORE_WEIGHTS:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0: raise ValueError(f"{name} must be in [0,1]")
        if self.fitness is not None and not 0.0 <= float(self.fitness) <= 1.0: raise ValueError("fitness must be in [0,1]")
        return self
    @property
    def score(self) -> float:
        self.validate(); metrics_are_default = all(float(getattr(self, name)) == 0.5 for name in _SCORE_WEIGHTS)
        if metrics_are_default and self.fitness is not None: return round(float(self.fitness), 8)
        positive = _SCORE_WEIGHTS["quality"]*self.quality + _SCORE_WEIGHTS["reliability"]*self.reliability + _SCORE_WEIGHTS["freshness"]*self.freshness + _SCORE_WEIGHTS["proof_strength"]*self.proof_strength
        penalty_cap = sum(_SCORE_WEIGHTS[k] for k in ("latency","cost","owner_burden","risk")); penalties = _SCORE_WEIGHTS["latency"]*self.latency + _SCORE_WEIGHTS["cost"]*self.cost + _SCORE_WEIGHTS["owner_burden"]*self.owner_burden + _SCORE_WEIGHTS["risk"]*self.risk
        return round(positive + (penalty_cap - penalties), 8)


@dataclass(frozen=True)
class RouteDecision:
    selected_route_id: str; blocked_routes: tuple[str, ...]; reasons: tuple[str, ...]; route_scores: tuple[tuple[str, float], ...]; disposition: RouteDisposition; next_action: str


class CapabilitySelector:
    def select(self, *, routes: Sequence[CapabilityRoute], memories: Sequence[FailureMemoryRecord], authority_ceiling: str = "A1_INTERNAL") -> RouteDecision:
        if not routes: raise ValueError("at least one route is required")
        allowed: list[CapabilityRoute] = []; blocked: list[str] = []; reasons: list[str] = []; scores: list[tuple[str,float]] = []; gate = FailureMemoryGate()
        for route in routes:
            route.validate(); scores.append((route.route_id, route.score)); route_reasons: list[str] = []
            if route.readiness != "READY": route_reasons.append(f"NOT_READY:{route.readiness}")
            if _REALITY_RANK[route.reality_state] < _REALITY_RANK[route.required_reality_state]: route_reasons.append("REALITY_INSUFFICIENT")
            if _AUTHORITY_RANK[route.authority_required] > _AUTHORITY_RANK.get(authority_ceiling, -1): route_reasons.append("AUTHORITY_CEILING_EXCEEDED")
            if route.external_effect and _AUTHORITY_RANK.get(authority_ceiling, 0) <= _AUTHORITY_RANK["A1_INTERNAL"]: route_reasons.append("EXTERNAL_EFFECT_NOT_AUTHORISED")
            route_reasons.extend(gate.blockers(route_id=route.route_id, memories=memories, retry_evidence_refs=route.retry_evidence_refs))
            if route_reasons: blocked.append(route.route_id); reasons.extend(f"{route.route_id}:{reason}" for reason in route_reasons)
            else: allowed.append(route)
        scores_tuple = tuple(sorted(scores))
        if not allowed: return RouteDecision("", tuple(sorted(set(blocked))), tuple(sorted(set(reasons))), scores_tuple, RouteDisposition.REPAIR, "FORM_OR_REPAIR_ROUTE")
        winner = max(allowed, key=lambda route: (route.score, route.route_id))
        return RouteDecision(winner.route_id, tuple(sorted(set(blocked))), tuple(sorted(set(reasons))), scores_tuple, RouteDisposition.SELECT, "EXECUTE_SELECTED_ROUTE")


@dataclass(frozen=True)
class NearMissEvent:
    mission_id: str; route_id: str; prevented_action: str; prevention_reason: str; proof_refs: tuple[str, ...]; event_digest: str
    @classmethod
    def create(cls, *, mission_id: str, route_id: str, prevented_action: str, prevention_reason: str, proof_refs: Iterable[str]) -> "NearMissEvent":
        _validate_id(mission_id, "mission_id"); _validate_id(route_id, "route_id"); refs = tuple(sorted({str(ref).strip() for ref in proof_refs if str(ref).strip()}))
        if not refs: raise ValueError("near miss requires proof references")
        body = {"mission_id": mission_id, "route_id": route_id, "prevented_action": str(prevented_action), "prevention_reason": str(prevention_reason), "proof_refs": refs}
        return cls(**body, event_digest=_digest(body))


@dataclass(frozen=True)
class ExecutionEnvelope:
    mission_id: str; operation_id: str; authorization_ref: str = ""; execution_ref: str = ""; target_readback_ref: str = ""; expected_target_digest: str = ""; observed_target_digest: str = ""; receipt_ref: str = ""
    @property
    def proof_state(self) -> str:
        if not self.authorization_ref: return ProofState.UNVERIFIED.value
        if not self.execution_ref: return ProofState.AUTHORISED.value
        if not self.target_readback_ref or not self.expected_target_digest or self.expected_target_digest != self.observed_target_digest: return ProofState.EXECUTED.value
        if not self.receipt_ref: return ProofState.READBACK_VERIFIED.value
        return ProofState.RECEIPT_VERIFIED.value
    @property
    def completion_claim_allowed(self) -> bool: return self.proof_state == ProofState.RECEIPT_VERIFIED.value


@dataclass(frozen=True)
class MissionSnapshot:
    mission_id: str; current_main_sha: str; concurrency_state: str; selected_route_id: str; blocked_routes: tuple[str, ...]; failure_fingerprints: tuple[str, ...]; route_scores: tuple[tuple[str, float], ...]; near_miss_refs: tuple[str, ...]; next_action: str; snapshot_sha256: str
    @classmethod
    def create(cls, *, lease: MissionLease, current_main_sha: str, concurrency: ConcurrencyDecision, selection: RouteDecision, memories: Sequence[FailureMemoryRecord] = (), near_misses: Sequence[NearMissEvent] = ()) -> "MissionSnapshot":
        _validate_sha(current_main_sha, "current_main_sha"); body = {"mission_id": lease.mission_id, "current_main_sha": current_main_sha, "concurrency_state": concurrency.state.value, "selected_route_id": selection.selected_route_id, "blocked_routes": selection.blocked_routes, "failure_fingerprints": tuple(sorted({m.fingerprint for m in memories})), "route_scores": selection.route_scores, "near_miss_refs": tuple(sorted({n.event_digest for n in near_misses})), "next_action": concurrency.next_action if not concurrency.write_allowed else selection.next_action}
        return cls(**body, snapshot_sha256=_digest(body))
    def as_dict(self) -> dict[str, object]: return asdict(self)


__all__ = ["CapabilityRoute","CapabilitySelector","ConcurrencyDecision","ConcurrencyGuard","ConcurrencyState","ExecutionEnvelope","FailureMemoryGate","FailureMemoryRecord","FailureStatus","MissionLease","MissionSnapshot","NearMissEvent","PreWriteFence","PreWriteFenceReceipt","ProofState","RouteDecision","RouteDisposition","WorkstreamObservation","overlapping_paths"]
