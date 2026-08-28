from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping, Sequence

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


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _clean_paths(values: Iterable[str]) -> tuple[str, ...]:
    cleaned: set[str] = set()
    for raw in values:
        value = str(raw).strip().replace("\\", "/")
        if not value:
            continue
        if value.startswith("/"):
            raise ValueError("path scope must be repository-relative")
        while value.startswith("./"):
            value = value[2:]
        parts = value.split("/")
        if not value or any(part in {"", ".."} for part in parts):
            raise ValueError("path scope must be repository-relative and traversal-free")
        cleaned.add(value.rstrip("/"))
    if not cleaned:
        raise ValueError("at least one repository path is required")
    return tuple(sorted(cleaned))


def _validate_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value


def _validate_sha(value: str, field: str = "sha") -> str:
    if not isinstance(value, str) or not _SHA40.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase 40-character Git SHA")
    return value


def _path_overlap(left: str, right: str) -> bool:
    left = left.rstrip("/")
    right = right.rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def overlapping_paths(left: Iterable[str], right: Iterable[str]) -> tuple[str, ...]:
    lhs = _clean_paths(left)
    rhs = _clean_paths(right)
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
    """Mission/path lease used as a fencing token, not as provider authority."""

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
        paths = _clean_paths(path_scope)
        issued = _parse_time(issued_at)
        expires = _parse_time(expires_at)
        if expires <= issued:
            raise ValueError("lease expiry must be after issuance")
        level = _AUTHORITY_RANK.get(authority_ceiling)
        if level is None or level > _AUTHORITY_RANK["A1_INTERNAL"] or external_effect:
            raise ValueError("mission lease cannot create provider/external authority")
        body = {
            "mission_id": mission_id,
            "lane_id": lane_id,
            "holder_id": holder_id,
            "base_main_sha": base_main_sha,
            "lease_epoch": lease_epoch,
            "path_scope": paths,
            "issued_at": issued.isoformat(),
            "expires_at": expires.isoformat(),
            "authority_ceiling": authority_ceiling,
            "external_effect": False,
        }
        return cls(fence_token=f"FMACF-FENCE-{_digest(body)[:32].upper()}", **body)

    def active_at(self, now: str) -> bool:
        instant = _parse_time(now)
        return _parse_time(self.issued_at) <= instant < _parse_time(self.expires_at)

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
    head_sha: str
    base_sha: str
    paths: tuple[str, ...]
    state: str = "OPEN"

    @classmethod
    def create(
        cls,
        *,
        workstream_id: str,
        head_sha: str,
        base_sha: str,
        paths: Iterable[str],
        state: str = "OPEN",
    ) -> "WorkstreamObservation":
        _validate_id(workstream_id, "workstream_id")
        return cls(
            workstream_id=workstream_id,
            head_sha=_validate_sha(head_sha, "head_sha"),
            base_sha=_validate_sha(base_sha, "base_sha"),
            paths=_clean_paths(paths),
            state=str(state).upper(),
        )


@dataclass(frozen=True)
class ConcurrencyDecision:
    state: ConcurrencyState
    write_allowed: bool
    current_main_sha: str
    lease_main_sha: str
    overlapping_workstreams: tuple[str, ...]
    overlapping_paths: tuple[str, ...]
    next_action: str


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
        if not lease.active_at(now):
            return ConcurrencyDecision(
                state=ConcurrencyState.LEASE_EXPIRED,
                write_allowed=False,
                current_main_sha=current_main_sha,
                lease_main_sha=lease.base_main_sha,
                overlapping_workstreams=(),
                overlapping_paths=(),
                next_action="RENEW_LEASE_FROM_FRESH_MAIN",
            )

        workstream_hits: list[str] = []
        path_hits: set[str] = set()
        for item in active_workstreams:
            if item.state not in {"OPEN", "DRAFT", "RUNNING", "READY"}:
                continue
            hits = overlapping_paths(lease.path_scope, item.paths)
            if hits:
                workstream_hits.append(item.workstream_id)
                path_hits.update(hits)

        if workstream_hits:
            return ConcurrencyDecision(
                state=ConcurrencyState.ACTIVE_WORKSTREAM_OVERLAP_HOLD,
                write_allowed=False,
                current_main_sha=current_main_sha,
                lease_main_sha=lease.base_main_sha,
                overlapping_workstreams=tuple(sorted(set(workstream_hits))),
                overlapping_paths=tuple(sorted(path_hits)),
                next_action="RECONCILE_OR_SERIALIZE_OVERLAPPING_WORKSTREAMS",
            )

        if current_main_sha != lease.base_main_sha:
            changed = tuple(str(p) for p in main_changed_paths if str(p).strip())
            hits = overlapping_paths(lease.path_scope, changed) if changed else ()
            if hits:
                return ConcurrencyDecision(
                    state=ConcurrencyState.MAIN_DRIFT_OVERLAP_HOLD,
                    write_allowed=False,
                    current_main_sha=current_main_sha,
                    lease_main_sha=lease.base_main_sha,
                    overlapping_workstreams=(),
                    overlapping_paths=hits,
                    next_action="RECONCILE_CHANGED_PATHS_AND_REISSUE_LEASE",
                )
            return ConcurrencyDecision(
                state=ConcurrencyState.MAIN_DRIFT_FAST_RECONVERGE,
                write_allowed=False,
                current_main_sha=current_main_sha,
                lease_main_sha=lease.base_main_sha,
                overlapping_workstreams=(),
                overlapping_paths=(),
                next_action="FAST_RECONVERGE_ON_CURRENT_MAIN_AND_REISSUE_LEASE",
            )

        return ConcurrencyDecision(
            state=ConcurrencyState.CLEAR,
            write_allowed=True,
            current_main_sha=current_main_sha,
            lease_main_sha=lease.base_main_sha,
            overlapping_workstreams=(),
            overlapping_paths=(),
            next_action="WRITE_WITH_FENCE_TOKEN_AND_POST_WRITE_READBACK",
        )


@dataclass(frozen=True)
class PreWriteFenceReceipt:
    mission_id: str
    lease_epoch: int
    base_main_sha: str
    current_main_sha: str
    fence_token: str
    path_digest: str
    allowed: bool
    reason: str
    receipt_digest: str


class PreWriteFence:
    """CAS-style guard: a source mutation is valid only against fresh main truth."""

    def authorise(
        self,
        *,
        lease: MissionLease,
        decision: ConcurrencyDecision,
        intended_paths: Iterable[str],
    ) -> PreWriteFenceReceipt:
        paths = _clean_paths(intended_paths)
        if any(not any(_path_overlap(path, scope) for scope in lease.path_scope) for path in paths):
            allowed = False
            reason = "INTENDED_PATH_OUTSIDE_LEASE_SCOPE"
        elif not decision.write_allowed:
            allowed = False
            reason = decision.state.value
        elif decision.current_main_sha != lease.base_main_sha:
            allowed = False
            reason = "STALE_MAIN_FENCE"
        else:
            allowed = True
            reason = "PREWRITE_FENCE_VERIFIED"
        body = {
            "mission_id": lease.mission_id,
            "lease_epoch": lease.lease_epoch,
            "base_main_sha": lease.base_main_sha,
            "current_main_sha": decision.current_main_sha,
            "fence_token": lease.fence_token,
            "path_digest": _digest(paths),
            "allowed": allowed,
            "reason": reason,
        }
        return PreWriteFenceReceipt(receipt_digest=_digest(body), **body)


@dataclass(frozen=True)
class FailureMemoryRecord:
    fingerprint: str
    route_id: str
    status: FailureStatus
    failure_proof_ref: str
    retry_condition: str
    recovery_proof_ref: str = ""

    def validate(self) -> "FailureMemoryRecord":
        if len(self.fingerprint.strip()) < 6:
            raise ValueError("failure fingerprint is too short")
        _validate_id(self.route_id, "route_id")
        if not self.failure_proof_ref.strip() or not self.retry_condition.strip():
            raise ValueError("failure record requires proof and retry condition")
        if self.status == FailureStatus.CLOSED and not self.recovery_proof_ref.strip():
            raise ValueError("closed failure requires recovery proof")
        return self


@dataclass(frozen=True)
class CapabilityRoute:
    route_id: str
    capability_id: str
    reality_state: str
    readiness: str
    proof_ref: str
    required_reality_state: str = "C3"
    authority_required: str = "A1_INTERNAL"
    external_effect: bool = False
    retry_evidence_refs: tuple[str, ...] = ()
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
        if not self.proof_ref.strip():
            raise ValueError("route requires a proof reference")
        if self.readiness not in {"READY", "HOLD", "BLOCKED", "STALE"}:
            raise ValueError("unknown readiness")
        if self.authority_required not in _AUTHORITY_RANK:
            raise ValueError("unknown authority requirement")
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
            reasons.append(f"ROUTE_NOT_READY:{route.readiness}")
        if _REALITY_RANK[route.reality_state] < _REALITY_RANK[route.required_reality_state]:
            reasons.append(
                f"REALITY_STATE_INSUFFICIENT:{route.reality_state}<{route.required_reality_state}"
            )
        if _AUTHORITY_RANK[route.authority_required] > _AUTHORITY_RANK[authority_ceiling]:
            reasons.append("AUTHORITY_CEILING_EXCEEDED")
        if route.external_effect and _AUTHORITY_RANK[authority_ceiling] <= _AUTHORITY_RANK["A1_INTERNAL"]:
            reasons.append("EXTERNAL_EFFECT_NOT_AUTHORISED")

        for memory in memories:
            memory.validate()
            if memory.route_id != route.route_id:
                continue
            if memory.status == FailureStatus.OPEN:
                reasons.append(f"KNOWN_OPEN_FAILURE:{memory.fingerprint}")
            elif memory.status == FailureStatus.MITIGATED:
                if not memory.recovery_proof_ref or memory.recovery_proof_ref not in route.retry_evidence_refs:
                    reasons.append(f"MITIGATION_PROOF_NOT_BOUND:{memory.fingerprint}")
            elif memory.status == FailureStatus.CLOSED:
                if memory.recovery_proof_ref not in route.retry_evidence_refs:
                    reasons.append(f"RECOVERY_PROOF_NOT_BOUND:{memory.fingerprint}")

        eligible = not reasons
        disposition = RouteDisposition.SELECT if eligible else RouteDisposition.HOLD
        return RouteGateDecision(
            route_id=route.route_id,
            disposition=disposition,
            eligible=eligible,
            score=route.score,
            reasons=tuple(reasons),
        )


@dataclass(frozen=True)
class RouteSelection:
    selected_route_id: str
    selected_capability_id: str
    selected_score: float
    blocked_routes: tuple[str, ...]
    decisions: tuple[RouteGateDecision, ...]
    next_action: str


class CapabilitySelector:
    """CFBE-style tournament after reality, failure-memory and authority gates."""

    def __init__(self) -> None:
        self.gate = FailureMemoryGate()

    def select(
        self,
        *,
        routes: Sequence[CapabilityRoute],
        memories: Sequence[FailureMemoryRecord],
        authority_ceiling: str = "A1_INTERNAL",
    ) -> RouteSelection:
        if not routes:
            raise ValueError("at least one candidate route is required")
        decisions = tuple(
            self.gate.evaluate(
                route=route,
                memories=memories,
                authority_ceiling=authority_ceiling,
            )
            for route in routes
        )
        by_id = {route.route_id: route for route in routes}
        eligible = [decision for decision in decisions if decision.eligible]
        blocked = tuple(sorted(decision.route_id for decision in decisions if not decision.eligible))
        if not eligible:
            return RouteSelection(
                selected_route_id="",
                selected_capability_id="",
                selected_score=0.0,
                blocked_routes=blocked,
                decisions=decisions,
                next_action="INVOKE_CAPABILITY_FORMATION_OR_MATERIAL_ROUTE_REPAIR",
            )
        winner = max(eligible, key=lambda item: (item.score, item.route_id))
        route = by_id[winner.route_id]
        return RouteSelection(
            selected_route_id=route.route_id,
            selected_capability_id=route.capability_id,
            selected_score=winner.score,
            blocked_routes=blocked,
            decisions=decisions,
            next_action="EXECUTE_SELECTED_ROUTE_THROUGH_AUTHORISED_CAPABILITY_HANDLE",
        )


@dataclass(frozen=True)
class ExecutionEnvelope:
    """RealityGuard-compatible proof envelope. It never performs the effect itself."""

    mission_id: str
    operation_id: str
    authorization_ref: str = ""
    execution_ref: str = ""
    target_readback_ref: str = ""
    receipt_ref: str = ""
    expected_target_digest: str = ""
    observed_target_digest: str = ""
    external_effect: bool = False

    @property
    def proof_state(self) -> ProofState:
        if not self.authorization_ref:
            return ProofState.UNVERIFIED
        if not self.execution_ref:
            return ProofState.AUTHORISED
        if not self.target_readback_ref:
            return ProofState.EXECUTED
        if not self.expected_target_digest or self.expected_target_digest != self.observed_target_digest:
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
        if not refs:
            raise ValueError("near miss requires proof refs")
        body = {
            "mission_id": mission_id,
            "event_type": str(event_type).strip(),
            "prevented_action": str(prevented_action).strip(),
            "signal": str(signal).strip(),
            "control": str(control).strip(),
            "proof_refs": refs,
        }
        if not all((body["event_type"], body["prevented_action"], body["signal"], body["control"])):
            raise ValueError("near miss fields must be non-empty")
        return cls(event_id=f"FMACF-NEARMISS-{_digest(body)[:24].upper()}", **body)


@dataclass(frozen=True)
class MissionSnapshot:
    mission_id: str
    current_main_sha: str
    lease_epoch: int
    fence_token: str
    concurrency_state: str
    selected_route_id: str
    blocked_routes: tuple[str, ...]
    active_failure_fingerprints: tuple[str, ...]
    near_miss_ids: tuple[str, ...]
    next_action: str
    snapshot_digest: str

    @classmethod
    def create(
        cls,
        *,
        lease: MissionLease,
        concurrency: ConcurrencyDecision,
        selection: RouteSelection,
        memories: Sequence[FailureMemoryRecord],
        near_misses: Sequence[NearMissEvent] = (),
    ) -> "MissionSnapshot":
        active_failures = tuple(
            sorted(
                memory.fingerprint
                for memory in memories
                if memory.status in {FailureStatus.OPEN, FailureStatus.MITIGATED}
            )
        )
        body = {
            "mission_id": lease.mission_id,
            "current_main_sha": concurrency.current_main_sha,
            "lease_epoch": lease.lease_epoch,
            "fence_token": lease.fence_token,
            "concurrency_state": concurrency.state.value,
            "selected_route_id": selection.selected_route_id,
            "blocked_routes": selection.blocked_routes,
            "active_failure_fingerprints": active_failures,
            "near_miss_ids": tuple(sorted(item.event_id for item in near_misses)),
            "next_action": (
                concurrency.next_action if not concurrency.write_allowed else selection.next_action
            ),
        }
        return cls(snapshot_digest=_digest(body), **body)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET = FailureMemoryRecord(
    fingerprint="GOOGLE_WIF_INVALID_TARGET",
    route_id="GITHUB_TO_GOOGLE_WIF",
    status=FailureStatus.OPEN,
    failure_proof_ref="governance/sovara_federation_capability_adoption_v1_1.json",
    retry_condition=(
        "Require a newer provider-native FEDOMEGA-WIF-CLOUD-VERIFIED receipt proving "
        "pool/provider existence, enabled state, repository/branch trust and service-account impersonation."
    ),
)


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
    "KNOWN_FAILURE_GOOGLE_WIF_INVALID_TARGET",
    "MissionLease",
    "MissionSnapshot",
    "NearMissEvent",
    "PreWriteFence",
    "PreWriteFenceReceipt",
    "ProofState",
    "RouteDisposition",
    "RouteGateDecision",
    "RouteSelection",
    "WorkstreamObservation",
    "overlapping_paths",
]
