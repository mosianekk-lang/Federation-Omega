from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Iterable, Sequence

_REALITY_RANK = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}
_AUTHORITY_RANK = {"A0": 0, "A0_READ": 0, "A1": 1, "A1_INTERNAL": 1, "A2": 2, "A3": 3}
_OPEN_STATES = {"OPEN", "DRAFT", "RUNNING", "READY"}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _paths(values: Iterable[str]) -> tuple[str, ...]:
    out: set[str] = set()
    for raw in values:
        value = str(raw).strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if not value or value.startswith("/") or any(part in {"", ".."} for part in value.split("/")):
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
    ) -> "MissionLease":
        if len(base_main_sha) != 40 or any(c not in "0123456789abcdef" for c in base_main_sha):
            raise ValueError("base_main_sha must be a lowercase Git SHA")
        if lease_epoch < 1:
            raise ValueError("lease_epoch must be positive")
        if _AUTHORITY_RANK.get(authority_ceiling, 99) > _AUTHORITY_RANK["A1_INTERNAL"]:
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


@dataclass(frozen=True)
class WorkstreamObservation:
    workstream_id: str
    base_sha: str
    head_sha: str
    paths: tuple[str, ...]
    state: str = "OPEN"

    @classmethod
    def create(cls, *, workstream_id: str, base_sha: str, head_sha: str, paths: Iterable[str], state: str = "OPEN") -> "WorkstreamObservation":
        return cls(workstream_id, base_sha, head_sha, _paths(paths), state.upper())


@dataclass(frozen=True)
class ConcurrencyDecision:
    state: str
    write_allowed: bool
    overlapping_workstreams: tuple[str, ...]
    overlapping_paths: tuple[str, ...]
    next_action: str


class ConcurrencyGuard:
    def evaluate(
        self,
        *,
        lease: MissionLease,
        current_main_sha: str,
        now: str,
        main_changed_paths: Iterable[str] = (),
        active_workstreams: Sequence[WorkstreamObservation] = (),
    ) -> ConcurrencyDecision:
        if not lease.active_at(now):
            return ConcurrencyDecision("LEASE_EXPIRED", False, (), (), "RENEW_FROM_FRESH_MAIN")
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
            return ConcurrencyDecision("ACTIVE_WORKSTREAM_OVERLAP_HOLD", False, tuple(sorted(streams)), tuple(sorted(hits)), "SERIALIZE_OR_RECONCILE")
        if current_main_sha != lease.base_main_sha:
            changed = tuple(str(x) for x in main_changed_paths if str(x).strip())
            overlap = overlapping_paths(lease.path_scope, changed) if changed else ()
            if overlap:
                return ConcurrencyDecision("MAIN_DRIFT_OVERLAP_HOLD", False, (), overlap, "RECONCILE_CHANGED_PATHS")
            return ConcurrencyDecision("MAIN_DRIFT_FAST_RECONVERGE", False, (), (), "RESTACK_ON_CURRENT_MAIN")
        return ConcurrencyDecision("CLEAR", True, (), (), "WRITE_WITH_FENCE_AND_READBACK")


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


class PreWriteFence:
    def authorise(self, *, lease: MissionLease, decision: ConcurrencyDecision, current_main_sha: str, intended_paths: Iterable[str]) -> PreWriteFenceReceipt:
        paths = _paths(intended_paths)
        inside_scope = all(any(_overlap(path, scope) for scope in lease.path_scope) for path in paths)
        if not inside_scope:
            allowed, reason = False, "PATH_OUTSIDE_LEASE_SCOPE"
        elif not decision.write_allowed:
            allowed, reason = False, decision.state
        elif current_main_sha != lease.base_main_sha:
            allowed, reason = False, "STALE_MAIN_FENCE"
        else:
            allowed, reason = True, "PREWRITE_FENCE_VERIFIED"
        body = {
            "mission_id": lease.mission_id,
            "base_main_sha": lease.base_main_sha,
            "current_main_sha": current_main_sha,
            "fence_token": lease.fence_token,
            "intended_paths_sha256": _digest(paths),
            "allowed": allowed,
            "reason": reason,
        }
        return PreWriteFenceReceipt(**body, receipt_sha256=_digest(body))


@dataclass(frozen=True)
class FailureMemoryRecord:
    fingerprint: str
    route_id: str
    status: str
    failure_proof_ref: str
    retry_condition: str
    recovery_proof_ref: str = ""

    def blockers_for(self, route_id: str, retry_evidence_refs: Iterable[str]) -> tuple[str, ...]:
        if route_id != self.route_id:
            return ()
        refs = set(retry_evidence_refs)
        state = self.status.upper()
        if state == "OPEN":
            return (f"KNOWN_OPEN_FAILURE:{self.fingerprint}",)
        if state in {"MITIGATED", "CLOSED"} and (not self.recovery_proof_ref or self.recovery_proof_ref not in refs):
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
    fitness: float = 0.5


@dataclass(frozen=True)
class RouteDecision:
    selected_route_id: str
    blocked_routes: tuple[str, ...]
    reasons: tuple[str, ...]
    next_action: str


class CapabilitySelector:
    def select(self, *, routes: Sequence[CapabilityRoute], memories: Sequence[FailureMemoryRecord], authority_ceiling: str = "A1_INTERNAL") -> RouteDecision:
        if not routes:
            raise ValueError("at least one route is required")
        allowed: list[CapabilityRoute] = []
        blocked: list[str] = []
        reasons: list[str] = []
        for route in routes:
            route_reasons: list[str] = []
            if route.readiness != "READY":
                route_reasons.append(f"NOT_READY:{route.readiness}")
            if _REALITY_RANK.get(route.reality_state, -1) < _REALITY_RANK.get(route.required_reality_state, 99):
                route_reasons.append("REALITY_INSUFFICIENT")
            if _AUTHORITY_RANK.get(route.authority_required, 99) > _AUTHORITY_RANK.get(authority_ceiling, -1):
                route_reasons.append("AUTHORITY_CEILING_EXCEEDED")
            if route.external_effect and _AUTHORITY_RANK.get(authority_ceiling, 0) <= _AUTHORITY_RANK["A1_INTERNAL"]:
                route_reasons.append("EXTERNAL_EFFECT_NOT_AUTHORISED")
            if not route.proof_ref:
                route_reasons.append("PROOF_REF_REQUIRED")
            for memory in memories:
                route_reasons.extend(memory.blockers_for(route.route_id, route.retry_evidence_refs))
            if route_reasons:
                blocked.append(route.route_id)
                reasons.extend(f"{route.route_id}:{r}" for r in route_reasons)
            else:
                allowed.append(route)
        if not allowed:
            return RouteDecision("", tuple(sorted(blocked)), tuple(sorted(reasons)), "FORM_OR_REPAIR_ROUTE")
        winner = max(allowed, key=lambda r: (r.fitness, r.route_id))
        return RouteDecision(winner.route_id, tuple(sorted(blocked)), tuple(sorted(reasons)), "EXECUTE_SELECTED_ROUTE")


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

    @property
    def proof_state(self) -> str:
        if not self.authorization_ref:
            return "UNVERIFIED"
        if not self.execution_ref:
            return "AUTHORISED"
        if not self.target_readback_ref or not self.expected_target_digest or self.expected_target_digest != self.observed_target_digest:
            return "EXECUTED"
        if not self.receipt_ref:
            return "READBACK_VERIFIED"
        return "RECEIPT_VERIFIED"

    @property
    def completion_claim_allowed(self) -> bool:
        return self.proof_state == "RECEIPT_VERIFIED"


@dataclass(frozen=True)
class MissionSnapshot:
    mission_id: str
    current_main_sha: str
    concurrency_state: str
    selected_route_id: str
    blocked_routes: tuple[str, ...]
    next_action: str
    snapshot_sha256: str

    @classmethod
    def create(cls, *, lease: MissionLease, current_main_sha: str, concurrency: ConcurrencyDecision, selection: RouteDecision) -> "MissionSnapshot":
        body = {
            "mission_id": lease.mission_id,
            "current_main_sha": current_main_sha,
            "concurrency_state": concurrency.state,
            "selected_route_id": selection.selected_route_id,
            "blocked_routes": selection.blocked_routes,
            "next_action": concurrency.next_action if not concurrency.write_allowed else selection.next_action,
        }
        return cls(**body, snapshot_sha256=_digest(body))

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


__all__ = [
    "CapabilityRoute", "CapabilitySelector", "ConcurrencyDecision", "ConcurrencyGuard",
    "ExecutionEnvelope", "FailureMemoryRecord", "MissionLease", "MissionSnapshot",
    "PreWriteFence", "PreWriteFenceReceipt", "RouteDecision", "WorkstreamObservation",
    "overlapping_paths",
]
