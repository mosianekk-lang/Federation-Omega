from __future__ import annotations

"""Typed contracts for Federation Living State & Evolution Fabric."""

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
import math
import re
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "FEDERATION-LIVING-STATE-EVOLUTION-FABRIC-V1"
VERSION = "1.0.0"
AUTHORITY_CEILING = "A1_INTERNAL"
EXTERNAL_EFFECTS = 0

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:/@-]{1,256}$")
_AUTHORITY_RANK = {
    "A0": 0,
    "A0_READ": 0,
    "A1": 1,
    "A1_INTERNAL": 1,
    "A2": 2,
    "A3": 3,
}


class NodeKind(StrEnum):
    SYSTEM = "SYSTEM"
    CAPABILITY = "CAPABILITY"
    PROVIDER = "PROVIDER"
    SURFACE = "SURFACE"
    ROUTE = "ROUTE"
    PROOF = "PROOF"
    FAILURE_DOMAIN = "FAILURE_DOMAIN"
    CONTEXT = "CONTEXT"
    SESSION = "SESSION"
    MISSION = "MISSION"
    WORKSTREAM = "WORKSTREAM"
    EVIDENCE = "EVIDENCE"
    CONTROL = "CONTROL"
    LEARNING = "LEARNING"
    RULE = "RULE"
    OPPORTUNITY = "OPPORTUNITY"
    EXPERIMENT = "EXPERIMENT"
    DEBT = "DEBT"


class EdgeKind(StrEnum):
    PROVIDES = "PROVIDES"
    DEPENDS_ON = "DEPENDS_ON"
    ROUTES_THROUGH = "ROUTES_THROUGH"
    PROVEN_BY = "PROVEN_BY"
    INVALIDATED_BY = "INVALIDATED_BY"
    SHARES_FAILURE_DOMAIN = "SHARES_FAILURE_DOMAIN"
    ACTIVE_IN = "ACTIVE_IN"
    BLOCKED_BY = "BLOCKED_BY"
    CORRELATES_WITH = "CORRELATES_WITH"
    CAUSES = "CAUSES"
    LEARNED_FROM = "LEARNED_FROM"
    SUPERSEDES = "SUPERSEDES"
    CHALLENGES = "CHALLENGES"
    HAS_ROLLBACK = "HAS_ROLLBACK"
    CONSUMES = "CONSUMES"
    IMPROVES = "IMPROVES"


class ProofMaturity(StrEnum):
    UNKNOWN = "UNKNOWN"
    DECLARED = "DECLARED"
    SOURCE_READBACK = "SOURCE_READBACK"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    RUNTIME_READBACK = "RUNTIME_READBACK"
    PROVIDER_READBACK = "PROVIDER_READBACK"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"


_PROOF_RANK = {
    ProofMaturity.UNKNOWN: 0,
    ProofMaturity.DECLARED: 1,
    ProofMaturity.SOURCE_READBACK: 2,
    ProofMaturity.DETERMINISTIC_TESTED: 3,
    ProofMaturity.RUNTIME_READBACK: 4,
    ProofMaturity.PROVIDER_READBACK: 5,
    ProofMaturity.RECEIPT_VERIFIED: 6,
}


class CausalStatus(StrEnum):
    NONE = "NONE"
    CORRELATION = "CORRELATION"
    CANDIDATE = "CANDIDATE"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class HealthState(StrEnum):
    HOMEOSTATIC = "HOMEOSTATIC"
    DRIFT = "DRIFT"
    UNMEASURED = "UNMEASURED"


class ReflexAction(StrEnum):
    CONTINUE = "CONTINUE"
    HOLD_EFFECTFUL_ROUTE = "HOLD_EFFECTFUL_ROUTE"
    REPROBE_PROOF = "REPROBE_PROOF"
    QUARANTINE = "QUARANTINE"
    REROUTE = "REROUTE"
    CHECKPOINT = "CHECKPOINT"
    COMPACT_CONTEXT = "COMPACT_CONTEXT"
    SCIENTIST_REVIEW = "SCIENTIST_REVIEW"
    REDESIGN_OR_ROLLBACK = "REDESIGN_OR_ROLLBACK"


class EvolutionState(StrEnum):
    CHAMPION = "CHAMPION"
    SHADOW = "SHADOW"
    RESERVE = "RESERVE"
    REJECTED = "REJECTED"
    PROMOTION_ELIGIBLE = "PROMOTION_ELIGIBLE"
    HOLD = "HOLD"


class LearningClass(StrEnum):
    FAILURE = "FAILURE"
    NEAR_MISS = "NEAR_MISS"
    OWNER_CORRECTION = "OWNER_CORRECTION"
    SUCCESS = "SUCCESS"
    CONSTRAINT = "CONSTRAINT"


class FabricError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _id(value: str, field_name: str = "id") -> str:
    value = str(value)
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"invalid {field_name}: {value!r}")
    return value


def _authority_ok(value: str, maximum: str = AUTHORITY_CEILING) -> bool:
    return value in _AUTHORITY_RANK and maximum in _AUTHORITY_RANK and _AUTHORITY_RANK[value] <= _AUTHORITY_RANK[maximum]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return vars(value)
    raise TypeError("adapter input must be mapping-like")


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _scope_compatible(left: str, right: str) -> bool:
    return left == right or left == "GLOBAL" or right == "GLOBAL"


@dataclass(frozen=True)
class Provenance:
    source_ref: str
    proof_ref: str
    observed_at: str
    proof_maturity: ProofMaturity = ProofMaturity.DECLARED
    ttl_seconds: int = 3600
    confidence: float = 0.5
    authority_ceiling: str = AUTHORITY_CEILING
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"
    source_class: str = "UNKNOWN"

    def validate(self) -> "Provenance":
        if not str(self.source_ref).strip() or not str(self.observed_at).strip():
            raise ValueError("source_ref and observed_at are required")
        _parse_time(self.observed_at)
        if self.proof_maturity != ProofMaturity.UNKNOWN and not str(self.proof_ref).strip():
            raise ValueError("non-unknown proof maturity requires proof_ref")
        if self.ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if not 0 <= float(self.confidence) <= 1:
            raise ValueError("confidence must be in [0,1]")
        if not _authority_ok(self.authority_ceiling):
            raise ValueError("provenance cannot expand authority")
        if not str(self.matter_scope).strip():
            raise ValueError("matter_scope required")
        return self

    def age_seconds(self, now: str) -> float:
        return max(0.0, (_parse_time(now) - _parse_time(self.observed_at)).total_seconds())

    def fresh_at(self, now: str) -> bool:
        return self.age_seconds(now) <= self.ttl_seconds

    @property
    def rank(self) -> int:
        return _PROOF_RANK[self.proof_maturity]


@dataclass(frozen=True)
class WorldNode:
    node_id: str
    kind: NodeKind
    label: str
    state: str
    payload: Mapping[str, Any]
    provenance: Provenance
    external_effect: bool = False

    def validate(self) -> "WorldNode":
        _id(self.node_id, "node_id")
        if not self.label.strip() or not self.state.strip():
            raise ValueError("node label/state required")
        self.provenance.validate()
        if self.external_effect:
            raise ValueError("living world nodes cannot themselves execute external effects")
        return self

    @property
    def fingerprint(self) -> str:
        return digest({
            "node_id": self.node_id,
            "kind": self.kind.value,
            "label": self.label,
            "state": self.state,
            "payload": dict(self.payload),
            "provenance": asdict(self.provenance),
        })


@dataclass(frozen=True)
class CausalEvidence:
    temporal_order: bool = False
    intervention_observed: bool = False
    mechanism_supported: bool = False
    falsifier_tested: bool = False
    independent_replication: bool = False
    evidence_refs: tuple[str, ...] = ()

    @property
    def verified(self) -> bool:
        return (
            self.temporal_order
            and self.falsifier_tested
            and (self.intervention_observed or self.mechanism_supported)
            and bool(self.evidence_refs)
        )


@dataclass(frozen=True)
class WorldEdge:
    edge_id: str
    source_id: str
    target_id: str
    kind: EdgeKind
    provenance: Provenance
    confidence: float = 0.5
    causal_status: CausalStatus = CausalStatus.NONE
    causal_evidence: CausalEvidence = field(default_factory=CausalEvidence)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self, nodes: Mapping[str, WorldNode] | None = None) -> "WorldEdge":
        _id(self.edge_id, "edge_id")
        _id(self.source_id, "source_id")
        _id(self.target_id, "target_id")
        self.provenance.validate()
        if not 0 <= float(self.confidence) <= 1:
            raise ValueError("edge confidence must be in [0,1]")
        if self.kind == EdgeKind.CAUSES:
            if self.causal_status != CausalStatus.VERIFIED or not self.causal_evidence.verified:
                raise ValueError("CAUSES edge requires verified causal evidence")
        elif self.causal_status == CausalStatus.VERIFIED and self.kind != EdgeKind.CAUSES:
            raise ValueError("verified causal status must use CAUSES edge")
        if nodes is not None:
            if self.source_id not in nodes or self.target_id not in nodes:
                raise ValueError("edge endpoints must exist")
            left = nodes[self.source_id].provenance.matter_scope
            right = nodes[self.target_id].provenance.matter_scope
            if not _scope_compatible(left, right):
                raise ValueError("cross-matter edge contamination blocked")
            if not _scope_compatible(self.provenance.matter_scope, left) or not _scope_compatible(self.provenance.matter_scope, right):
                raise ValueError("edge scope incompatible with endpoint scope")
        return self


@dataclass(frozen=True)
class ObservationEvent:
    sequence: int
    event_type: str
    object_id: str
    payload: Mapping[str, Any]
    event_digest: str
    prior_digest: str


@dataclass(frozen=True)
class StateEstimate:
    node_id: str
    state: str
    fresh: bool
    proof_maturity: str
    proof_rank: int
    confidence: float
    source_ref: str
    proof_ref: str
    observed_at: str
    split_brain: bool
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class RouteTelemetry:
    route_id: str
    mission_id: str
    observed_at: str
    success: bool
    latency_ms: float
    cost_units: float
    owner_burden: float
    proof_freshness: float
    proof_strength: float
    risk: float
    failure_domains: tuple[str, ...]
    proof_ref: str
    matter_scope: str = "GLOBAL"
    provider_effect: bool = False

    def validate(self) -> "RouteTelemetry":
        _id(self.route_id, "route_id")
        _id(self.mission_id, "mission_id")
        _parse_time(self.observed_at)
        if min(self.latency_ms, self.cost_units, self.owner_burden, self.risk) < 0:
            raise ValueError("telemetry costs cannot be negative")
        for name in ("proof_freshness", "proof_strength"):
            if not 0 <= float(getattr(self, name)) <= 1:
                raise ValueError(f"{name} must be in [0,1]")
        if not self.proof_ref.strip():
            raise ValueError("telemetry requires proof_ref")
        return self


@dataclass(frozen=True)
class RouteEstimate:
    route_id: str
    samples: int
    successes: int
    reliability: float
    evidence_weight: float
    proof_freshness: float
    proof_strength: float
    latency_penalty: float
    cost_penalty: float
    owner_burden_penalty: float
    risk_penalty: float
    score: float
    failure_domains: tuple[str, ...]
    measured: bool


@dataclass(frozen=True)
class RoutePortfolio:
    champion: str
    shadows: tuple[str, ...]
    reserves: tuple[str, ...]
    rejected: tuple[str, ...]
    hidden_spofs: tuple[str, ...]
    estimates: tuple[RouteEstimate, ...]


@dataclass(frozen=True)
class ContextState:
    context_id: str
    used_units: int
    capacity_units: int
    duplicate_ratio: float
    stale_items: int
    verified_facts: tuple[str, ...] = ()
    adverse_evidence: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    def validate(self) -> "ContextState":
        _id(self.context_id, "context_id")
        if self.capacity_units <= 0 or self.used_units < 0:
            raise ValueError("invalid context capacity")
        if not 0 <= self.duplicate_ratio <= 1:
            raise ValueError("duplicate_ratio must be in [0,1]")
        if self.stale_items < 0:
            raise ValueError("stale_items cannot be negative")
        return self

    @property
    def pressure(self) -> float:
        self.validate()
        return self.used_units / self.capacity_units

    @property
    def protected_items(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            self.verified_facts
            + self.adverse_evidence
            + self.contradictions
            + self.gaps
            + self.blockers
            + self.decisions
            + self.source_refs
        ))

    def action(self) -> str:
        pressure = self.pressure
        if pressure >= 0.90 or len(self.blockers) + len(self.contradictions) >= 8:
            return "CHECKPOINT_AND_HANDOFF"
        if pressure >= 0.72 or self.duplicate_ratio >= 0.30 or self.stale_items >= 12:
            return "PROTECTED_COMPACTION"
        return "NORMAL"


@dataclass(frozen=True)
class MissionLease:
    mission_id: str
    base_main_sha: str
    epoch: int
    paths: tuple[str, ...]
    issued_at: str
    expires_at: str
    effectful: bool = False

    def validate(self) -> "MissionLease":
        _id(self.mission_id, "mission_id")
        if not _SHA40.fullmatch(self.base_main_sha):
            raise ValueError("base_main_sha must be lowercase SHA40")
        if self.epoch < 1 or not self.paths:
            raise ValueError("lease epoch/paths invalid")
        if _parse_time(self.expires_at) <= _parse_time(self.issued_at):
            raise ValueError("lease expiry must follow issue")
        return self

    def active_at(self, now: str) -> bool:
        self.validate()
        instant = _parse_time(now)
        return _parse_time(self.issued_at) <= instant < _parse_time(self.expires_at)


def _clean_path(path: str) -> str:
    value = str(path).replace("\\", "/").strip().lstrip("./")
    if not value or value.startswith("/") or ".." in value.split("/"):
        raise ValueError("unsafe path")
    return value.rstrip("/")


def _overlap(a: str, b: str) -> bool:
    a, b = _clean_path(a), _clean_path(b)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


@dataclass(frozen=True)
class ConcurrencyResult:
    allowed: bool
    disposition: str
    reason: str
    overlapping_paths: tuple[str, ...]


@dataclass(frozen=True)
class LearningEvent:
    learning_id: str
    learning_class: LearningClass
    fingerprint: str
    observed_at: str
    matter_scope: str
    route_id: str
    signal: str
    diagnosis: str
    hypothesis: str
    test_ref: str
    result_ref: str
    proof_refs: tuple[str, ...]
    recurrence: int
    independent_evidence: bool
    privacy_sensitive: bool = False

    def validate(self) -> "LearningEvent":
        _id(self.learning_id, "learning_id")
        if len(self.fingerprint.strip()) < 6:
            raise ValueError("learning fingerprint too short")
        _parse_time(self.observed_at)
        if self.recurrence < 1 or not self.proof_refs:
            raise ValueError("learning requires recurrence and proof")
        if not self.signal.strip() or not self.diagnosis.strip():
            raise ValueError("learning signal/diagnosis required")
        return self

    @property
    def escalation(self) -> str:
        if self.recurrence == 1:
            return "STRENGTHEN_CONTROL"
        if self.recurrence == 2:
            return "OMEGA_SCIENTIST_REVIEW"
        return "REDESIGN_OR_ROLLBACK"

    @property
    def global_promotion_allowed(self) -> bool:
        return self.matter_scope == "GLOBAL" and self.independent_evidence and not self.privacy_sensitive


@dataclass(frozen=True)
class PlannerCandidate:
    action_id: str
    mission_delta_reduction: float
    information_gain: float
    proof_gain: float
    reversibility: float
    risk: float
    cost: float
    owner_burden: float
    authority_required: str = AUTHORITY_CEILING
    external_effect: bool = False
    proof_ref: str = ""

    def validate(self) -> "PlannerCandidate":
        _id(self.action_id, "action_id")
        for name in (
            "mission_delta_reduction", "information_gain", "proof_gain", "reversibility",
            "risk", "cost", "owner_burden",
        ):
            value = float(getattr(self, name))
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0,1]")
        if not _authority_ok(self.authority_required):
            raise ValueError("planner candidate exceeds living-fabric authority")
        if not self.proof_ref.strip():
            raise ValueError("planner candidate needs proof_ref")
        return self

    @property
    def utility(self) -> float:
        self.validate()
        return round(
            0.30 * self.mission_delta_reduction
            + 0.23 * self.information_gain
            + 0.16 * self.proof_gain
            + 0.11 * self.reversibility
            - 0.09 * self.risk
            - 0.06 * self.cost
            - 0.05 * self.owner_burden,
            8,
        )


@dataclass(frozen=True)
class PlannerDecision:
    selected_action_id: str
    utility: float
    disposition: str
    rejected: tuple[str, ...]
    external_effect_executed: bool = False


@dataclass(frozen=True)
class EvolutionCandidate:
    capability_id: str
    role: str
    regression_passed: bool
    forward_canary_passed: bool
    independent_readback: bool
    rollback_available: bool
    baseline_score: float
    challenger_score: float
    sample_count: int
    proof_refs: tuple[str, ...]
    external_effect: bool = False

    def validate(self) -> "EvolutionCandidate":
        _id(self.capability_id, "capability_id")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")
        if not 0 <= self.baseline_score <= 1 or not 0 <= self.challenger_score <= 1:
            raise ValueError("scores must be in [0,1]")
        if not self.proof_refs:
            raise ValueError("evolution candidate requires proof refs")
        if self.external_effect:
            raise ValueError("living fabric cannot promote an external effect executor")
        return self

    @property
    def state(self) -> EvolutionState:
        self.validate()
        if not (
            self.regression_passed
            and self.forward_canary_passed
            and self.independent_readback
            and self.rollback_available
        ):
            return EvolutionState.SHADOW
        if self.sample_count < 3:
            return EvolutionState.SHADOW
        if self.challenger_score <= self.baseline_score:
            return EvolutionState.REJECTED
        return EvolutionState.PROMOTION_ELIGIBLE
