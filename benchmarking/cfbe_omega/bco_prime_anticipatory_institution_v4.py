from __future__ import annotations

"""BCΩ-PRIME v4 — Anticipatory Institutional Intelligence.

This module is a thin, non-sovereign composition layer over existing Federation
owners. It binds BCΩ-PRIME v1 meta-decisions to Formation FCI multi-timescale
planning, SOE capability pressure, HORIZON-Ω adaptive lookahead and the existing
capability-market semantics.

V4 adds the missing assurance boundary: capability underuse becomes machine-
observable and can block terminality; future demand can create bounded shadow
preparation proposals; capability dormancy/router bias can be challenged; and
new-build proposals are rejected when existing capability coverage is sufficient.

It does not add a scheduler, provider executor, authority plane, memory root,
proof plane, credential broker, background daemon or stable self-promotion path.
All v4 output is decision support / shadow preparation. Provider and
consequential effects remain separately authorised and independently read back.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from itertools import combinations
from typing import Iterable, Mapping, Sequence

from ao_harmonic_v3.horizon import HorizonOmega
from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import (
    PrimeDecisionIR,
    PrimeObservation,
    StrategyCandidate,
    compile_prime_decision,
)
from formation_omega.autonomic_fabric import AuthorityCeiling
from formation_omega.institutional_cognition import (
    Horizon,
    HorizonObjective,
    ImprovementCandidate,
    MultiTimescalePlanner,
    RecursiveImprovementGate,
)
from formation_omega.strategic_ecology import CapabilityCentrality, MissionCandidate


SCHEMA = "BCO_PRIME_ANTICIPATORY_INSTITUTION_V4"
UNDERUSE_RELEVANCE_THRESHOLD = 0.35
NEW_BUILD_EXISTING_COVERAGE_CEILING = 0.70
NEW_BUILD_MIN_DEMAND = 0.55


class V4Mode(str, Enum):
    SHADOW_ONLY = "SHADOW_ONLY"
    HOLD_CAPABILITY_UNDERUSE = "HOLD_CAPABILITY_UNDERUSE"


class CapabilityAction(str, Enum):
    KEEP = "KEEP"
    STRENGTHEN_EXISTING_OWNER = "STRENGTHEN_EXISTING_OWNER"
    ROUTER_CHALLENGE = "ROUTER_CHALLENGE"
    SHADOW_INVESTMENT = "SHADOW_INVESTMENT"
    COMPOSE = "COMPOSE"
    RETIREMENT_COURT = "RETIREMENT_COURT"
    HOLD_PROVIDER = "HOLD_PROVIDER"


class BuildDecision(str, Enum):
    REUSE_OR_EXTEND = "REUSE_OR_EXTEND"
    COMPOSE_EXISTING = "COMPOSE_EXISTING"
    CANDIDATE_NEW_CAPABILITY = "CANDIDATE_NEW_CAPABILITY"
    HOLD_INSUFFICIENT_DEMAND = "HOLD_INSUFFICIENT_DEMAND"


class MutationDecision(str, Enum):
    HOLD = "HOLD"
    CANDIDATE_SHADOW_EVOLUTION = "CANDIDATE_SHADOW_EVOLUTION"


VALID_SKIP_REASONS = frozenset(
    {
        "NOT_RELEVANT",
        "STALE",
        "LOWER_FIT_THAN_SELECTED_ROUTE",
        "DUPLICATE_CAPABILITY",
        "AUTHORITY_HELD",
        "COST_EXCEEDS_VALUE",
        "DEPENDENCY_UNAVAILABLE",
        "UNSAFE_FOR_THIS_EFFECT",
        "SUPERSEDED",
        "PROVIDER_GATED",
    }
)


LIVEISH_STATES = frozenset(
    {
        "LIVE_VERIFIED",
        "OPERATIONAL_VERIFIED_SCOPED",
        "PROVEN",
        "PARTIAL",
        "CONNECTED_READ_ONLY",
    }
)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _receipt(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_sha(value: str, *, label: str) -> str:
    digest = value.strip().lower()
    if len(digest) != 40 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"{label}_INVALID")
    return digest


@dataclass(frozen=True, slots=True)
class CapabilitySignal:
    capability_id: str
    interfaces: tuple[str, ...]
    providers: tuple[str, ...]
    failure_domain: str
    state: str
    proof_age_hours: float
    eligible_missions: int
    used_missions: int
    successful_uses: int
    reliability: float
    owner_burden_reduction: float
    cost_efficiency: float
    failure_domain_uniqueness: float
    strategic_option_value: float
    maintenance_burden: float
    context_burden: float
    authority_ready: bool = False
    external_effect: bool = False
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> "CapabilitySignal":
        if not self.capability_id.strip():
            raise ValueError("V4_CAPABILITY_ID_REQUIRED")
        if not self.interfaces:
            raise ValueError("V4_CAPABILITY_INTERFACES_REQUIRED")
        if not self.providers:
            raise ValueError("V4_CAPABILITY_PROVIDERS_REQUIRED")
        if not self.failure_domain.strip():
            raise ValueError("V4_FAILURE_DOMAIN_REQUIRED")
        if self.proof_age_hours < 0:
            raise ValueError("V4_PROOF_AGE_NEGATIVE")
        if self.eligible_missions < 0 or self.used_missions < 0 or self.successful_uses < 0:
            raise ValueError("V4_CAPABILITY_COUNTS_NEGATIVE")
        if self.used_missions > self.eligible_missions:
            raise ValueError("V4_USED_EXCEEDS_ELIGIBLE")
        if self.successful_uses > self.used_missions:
            raise ValueError("V4_SUCCESS_EXCEEDS_USED")
        for name in (
            "reliability",
            "owner_burden_reduction",
            "cost_efficiency",
            "failure_domain_uniqueness",
            "strategic_option_value",
            "maintenance_burden",
            "context_burden",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"V4_{name.upper()}_OUT_OF_RANGE")
        return self

    @property
    def utilization_rate(self) -> float:
        return 0.0 if self.eligible_missions == 0 else self.used_missions / self.eligible_missions

    @property
    def success_rate(self) -> float:
        return 0.0 if self.used_missions == 0 else self.successful_uses / self.used_missions

    @property
    def proof_freshness(self) -> float:
        return 1.0 / (1.0 + self.proof_age_hours / 24.0)

    @property
    def net_fitness(self) -> float:
        self.validate()
        benefit = (
            0.22 * self.success_rate
            + 0.17 * _clip(self.reliability)
            + 0.13 * _clip(self.owner_burden_reduction)
            + 0.10 * _clip(self.cost_efficiency)
            + 0.10 * _clip(self.failure_domain_uniqueness)
            + 0.13 * _clip(self.strategic_option_value)
            + 0.15 * _clip(self.proof_freshness)
        )
        burden = 0.06 * _clip(self.maintenance_burden) + 0.04 * _clip(self.context_burden)
        return round(_clip(benefit - burden), 9)

    @property
    def dormancy_pressure(self) -> float:
        if self.eligible_missions == 0:
            return 0.0
        unused = 1.0 - _clip(self.utilization_rate)
        evidence_of_value = 0.55 * self.success_rate + 0.45 * self.net_fitness
        return round(_clip(unused * evidence_of_value), 9)


@dataclass(frozen=True, slots=True)
class CapabilityUseObservation:
    capability_id: str
    relevance: float
    used: bool
    skip_reason: str | None = None
    safe_parallelizable: bool = False
    executed_in_parallel: bool = False
    manual_user_fallback: bool = False
    executable_by_system: bool = False
    current_readback_available: bool = False
    current_readback_used: bool = False

    def validate(self) -> "CapabilityUseObservation":
        if not self.capability_id.strip():
            raise ValueError("V4_USE_CAPABILITY_ID_REQUIRED")
        if not 0.0 <= float(self.relevance) <= 1.0:
            raise ValueError("V4_USE_RELEVANCE_OUT_OF_RANGE")
        return self


@dataclass(frozen=True, slots=True)
class CapabilityUtilizationReceipt:
    relevant_capabilities: int
    used_relevant_capabilities: int
    justified_skips: int
    unjustified_skips: tuple[str, ...]
    manual_work_leaks: tuple[str, ...]
    parallelism_underuse: tuple[str, ...]
    freshness_underuse: tuple[str, ...]
    relevant_usage_ratio: float
    safe_parallelism_ratio: float
    automation_coverage_ratio: float
    freshness_coverage_ratio: float
    terminality_allowed: bool
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class DemandSignal:
    demand_id: str
    horizon: Horizon
    required_interfaces: tuple[str, ...]
    probability: float
    value: float
    urgency: float
    option_value: float
    dependency_centrality: float
    evidence_strength: float
    uncertainty: float
    external_effect: bool = False
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> "DemandSignal":
        if not self.demand_id.strip():
            raise ValueError("V4_DEMAND_ID_REQUIRED")
        if not self.required_interfaces:
            raise ValueError("V4_DEMAND_INTERFACES_REQUIRED")
        for name in (
            "probability",
            "value",
            "urgency",
            "option_value",
            "dependency_centrality",
            "evidence_strength",
            "uncertainty",
        ):
            if not 0.0 <= float(getattr(self, name)) <= 1.0:
                raise ValueError(f"V4_{name.upper()}_OUT_OF_RANGE")
        return self

    @property
    def demand_weight(self) -> float:
        return round(
            _clip(self.probability)
            * (0.35 * _clip(self.value) + 0.20 * _clip(self.urgency) + 0.20 * _clip(self.option_value)
               + 0.15 * _clip(self.dependency_centrality) + 0.10 * _clip(self.evidence_strength)),
            9,
        )


@dataclass(frozen=True, slots=True)
class CapabilityOpportunity:
    capability_id: str
    demand_score: float
    pressure_score: float
    net_fitness: float
    dormancy_pressure: float
    recommended_action: CapabilityAction
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompositionCandidate:
    capability_ids: tuple[str, str]
    demand_coverage: float
    mean_fitness: float
    failure_domain_diversity: float
    burden: float
    composition_score: float


@dataclass(frozen=True, slots=True)
class BuildGateDecision:
    decision: BuildDecision
    existing_interface_coverage: float
    future_demand_score: float
    reason_codes: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class MutationGateDecision:
    decision: MutationDecision
    blockers: tuple[str, ...]
    stable_self_promotion_allowed: bool
    external_effect_authorized: bool
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class V4DecisionIR:
    schema: str
    mode: V4Mode
    source_head_sha: str
    mission_id: str
    prime_v1_receipt_sha256: str
    utilization_receipt: CapabilityUtilizationReceipt
    selected_demand_ids: tuple[str, ...]
    interface_pressure: tuple[tuple[str, float], ...]
    capability_opportunities: tuple[CapabilityOpportunity, ...]
    composition_candidates: tuple[CompositionCandidate, ...]
    horizon_depth: int
    preparatory_actions: tuple[str, ...]
    owner_interrupt_required: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    stable_self_promotion_allowed: bool
    proof_requirements: tuple[str, ...]
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def canonical_mapping(self, *, include_receipt: bool = True) -> dict[str, object]:
        body = asdict(self)
        if not include_receipt:
            body.pop("receipt_sha256", None)
        return body


def capability_utilization_court(
    observations: Iterable[CapabilityUseObservation],
    *,
    relevance_threshold: float = UNDERUSE_RELEVANCE_THRESHOLD,
) -> CapabilityUtilizationReceipt:
    if not 0.0 <= relevance_threshold <= 1.0:
        raise ValueError("V4_RELEVANCE_THRESHOLD_INVALID")
    items = tuple(item.validate() for item in observations)
    relevant = tuple(item for item in items if item.relevance >= relevance_threshold)
    used = tuple(item for item in relevant if item.used)
    justified: list[str] = []
    unjustified: list[str] = []
    manual: list[str] = []
    parallel: list[str] = []
    freshness: list[str] = []
    for item in relevant:
        if not item.used:
            reason = (item.skip_reason or "").strip().upper()
            if reason in VALID_SKIP_REASONS:
                justified.append(item.capability_id)
            else:
                unjustified.append(item.capability_id)
        if item.manual_user_fallback and item.executable_by_system:
            manual.append(item.capability_id)
        if item.used and item.safe_parallelizable and not item.executed_in_parallel:
            parallel.append(item.capability_id)
        if item.current_readback_available and not item.current_readback_used:
            freshness.append(item.capability_id)
    relevant_count = len(relevant)
    parallelizable = [item for item in relevant if item.used and item.safe_parallelizable]
    automatable = [item for item in relevant if item.executable_by_system]
    freshenable = [item for item in relevant if item.current_readback_available]
    usage_ratio = 1.0 if relevant_count == 0 else (len(used) + len(justified)) / relevant_count
    parallel_ratio = 1.0 if not parallelizable else sum(item.executed_in_parallel for item in parallelizable) / len(parallelizable)
    automation_ratio = 1.0 if not automatable else 1.0 - (len(manual) / len(automatable))
    freshness_ratio = 1.0 if not freshenable else sum(item.current_readback_used for item in freshenable) / len(freshenable)
    terminality = not (unjustified or manual or parallel or freshness)
    body = {
        "relevant": relevant_count,
        "used": len(used),
        "justified": sorted(justified),
        "unjustified": sorted(unjustified),
        "manual": sorted(manual),
        "parallel": sorted(parallel),
        "freshness": sorted(freshness),
        "usage_ratio": round(usage_ratio, 9),
        "parallel_ratio": round(parallel_ratio, 9),
        "automation_ratio": round(automation_ratio, 9),
        "freshness_ratio": round(freshness_ratio, 9),
        "terminality": terminality,
    }
    return CapabilityUtilizationReceipt(
        relevant_capabilities=relevant_count,
        used_relevant_capabilities=len(used),
        justified_skips=len(justified),
        unjustified_skips=tuple(sorted(unjustified)),
        manual_work_leaks=tuple(sorted(manual)),
        parallelism_underuse=tuple(sorted(parallel)),
        freshness_underuse=tuple(sorted(freshness)),
        relevant_usage_ratio=round(usage_ratio, 9),
        safe_parallelism_ratio=round(parallel_ratio, 9),
        automation_coverage_ratio=round(automation_ratio, 9),
        freshness_coverage_ratio=round(freshness_ratio, 9),
        terminality_allowed=terminality,
        receipt_sha256=_receipt(body),
    )


def select_future_demand(signals: Sequence[DemandSignal], *, slots: int = 8) -> tuple[DemandSignal, ...]:
    if slots < 1:
        raise ValueError("V4_DEMAND_SLOTS_INVALID")
    validated = tuple(signal.validate() for signal in signals)
    if not validated:
        return ()
    objectives = tuple(
        HorizonObjective(
            objective_id=signal.demand_id,
            horizon=signal.horizon,
            value=_clip(signal.value * signal.probability * signal.evidence_strength),
            urgency=signal.urgency,
            option_value=signal.option_value,
            dependency_centrality=signal.dependency_centrality,
        )
        for signal in validated
    )
    selected_ids = {item.objective_id for item in MultiTimescalePlanner().select(objectives, slots=min(slots, len(objectives)))}
    return tuple(signal for signal in validated if signal.demand_id in selected_ids)


def interface_pressure(signals: Sequence[DemandSignal]) -> tuple[tuple[str, float], ...]:
    if not signals:
        return ()
    missions = tuple(
        MissionCandidate(
            mission_id=f"V4-DEMAND-{signal.demand_id}",
            objective_id="BCO_PRIME_V4_ANTICIPATION",
            summary=f"Prepare for demand {signal.demand_id}",
            outcome_value=signal.value,
            unlock_leverage=signal.option_value,
            success_probability=_clip(signal.probability * signal.evidence_strength),
            learning_value=_clip(0.4 + 0.4 * signal.uncertainty),
            reusability=0.8,
            cost=0.1,
            risk=0.1 if not signal.external_effect else 0.35,
            latency=0.1,
            required_capabilities=tuple(sorted(set(signal.required_interfaces))),
            authority_ceiling=AuthorityCeiling.A1_INTERNAL,
            external_effect=False,
            owner_reserved=False,
            evidence_refs=signal.evidence_refs,
        )
        for signal in signals
    )
    pressure = CapabilityCentrality().measure(missions)
    if not pressure:
        return ()
    maximum = max(item.build_priority for item in pressure) or 1.0
    return tuple((item.capability, round(_clip(item.build_priority / maximum), 9)) for item in pressure)


def _demand_score(capability: CapabilitySignal, signals: Sequence[DemandSignal]) -> float:
    interfaces = set(capability.interfaces)
    score = 0.0
    total = 0.0
    for signal in signals:
        weight = signal.demand_weight
        total += weight
        required = set(signal.required_interfaces)
        if required:
            score += weight * (len(interfaces & required) / len(required))
    return 0.0 if total <= 0 else round(_clip(score / total), 9)


def capability_opportunities(
    capabilities: Sequence[CapabilitySignal],
    signals: Sequence[DemandSignal],
    pressure: Sequence[tuple[str, float]],
) -> tuple[CapabilityOpportunity, ...]:
    pressure_map = dict(pressure)
    results: list[CapabilityOpportunity] = []
    for capability in capabilities:
        capability.validate()
        demand = _demand_score(capability, signals)
        pressure_score = max((pressure_map.get(interface, 0.0) for interface in capability.interfaces), default=0.0)
        fitness = capability.net_fitness
        dormancy = capability.dormancy_pressure
        reasons: list[str] = []
        if capability.external_effect and not capability.authority_ready:
            action = CapabilityAction.HOLD_PROVIDER
            reasons.append("EXTERNAL_CAPABILITY_AUTHORITY_NOT_READY")
        elif (
            capability.eligible_missions >= 5
            and capability.utilization_rate < 0.35
            and capability.success_rate >= 0.75
            and fitness >= 0.60
            and demand >= 0.30
        ):
            action = CapabilityAction.ROUTER_CHALLENGE
            reasons.extend(("UNDEREXPLOITED_HIGH_FIT_CAPABILITY", "INCUMBENT_ROUTE_BIAS_TEST_REQUIRED"))
        elif demand >= 0.55 and fitness >= 0.62 and capability.state.upper() in LIVEISH_STATES:
            action = CapabilityAction.STRENGTHEN_EXISTING_OWNER
            reasons.append("HIGH_FUTURE_DEMAND_HIGH_FIT_EXISTING_CAPABILITY")
        elif demand >= 0.50 and capability.state.upper() in {"SOURCE_ONLY", "PARTIAL", "STALE", "UNVERIFIED"}:
            action = CapabilityAction.SHADOW_INVESTMENT
            reasons.append("FUTURE_DEMAND_REQUIRES_BOUNDED_QUALIFICATION")
        elif demand < 0.15 and fitness < 0.42 and capability.maintenance_burden >= 0.60:
            action = CapabilityAction.RETIREMENT_COURT
            reasons.append("LOW_DEMAND_LOW_FIT_HIGH_MAINTENANCE")
        else:
            action = CapabilityAction.KEEP
            reasons.append("CURRENT_CAPABILITY_POSTURE_ACCEPTABLE")
        results.append(
            CapabilityOpportunity(
                capability_id=capability.capability_id,
                demand_score=demand,
                pressure_score=round(pressure_score, 9),
                net_fitness=fitness,
                dormancy_pressure=dormancy,
                recommended_action=action,
                reason_codes=tuple(reasons),
            )
        )
    return tuple(sorted(results, key=lambda item: (-max(item.demand_score, item.dormancy_pressure, item.net_fitness), item.capability_id)))


def composition_search(
    capabilities: Sequence[CapabilitySignal],
    signals: Sequence[DemandSignal],
    *,
    max_results: int = 5,
) -> tuple[CompositionCandidate, ...]:
    if max_results < 1:
        raise ValueError("V4_COMPOSITION_MAX_RESULTS_INVALID")
    available = [
        item.validate()
        for item in capabilities
        if not (item.external_effect and not item.authority_ready)
    ]
    required = set(interface for signal in signals for interface in signal.required_interfaces)
    if not required or len(available) < 2:
        return ()
    results: list[CompositionCandidate] = []
    for left, right in combinations(sorted(available, key=lambda item: item.capability_id), 2):
        coverage = len((set(left.interfaces) | set(right.interfaces)) & required) / len(required)
        if coverage <= 0:
            continue
        diversity = 1.0 if left.failure_domain != right.failure_domain else 0.0
        mean_fitness = (left.net_fitness + right.net_fitness) / 2.0
        burden = (left.maintenance_burden + right.maintenance_burden + left.context_burden + right.context_burden) / 4.0
        score = _clip(0.42 * coverage + 0.30 * mean_fitness + 0.18 * diversity + 0.10 * ((left.strategic_option_value + right.strategic_option_value) / 2.0) - 0.10 * burden)
        results.append(
            CompositionCandidate(
                capability_ids=(left.capability_id, right.capability_id),
                demand_coverage=round(coverage, 9),
                mean_fitness=round(mean_fitness, 9),
                failure_domain_diversity=diversity,
                burden=round(burden, 9),
                composition_score=round(score, 9),
            )
        )
    return tuple(sorted(results, key=lambda item: (-item.composition_score, item.capability_ids))[:max_results])


def new_capability_build_gate(
    *,
    required_interfaces: Iterable[str],
    existing_capabilities: Sequence[CapabilitySignal],
    future_signals: Sequence[DemandSignal],
) -> BuildGateDecision:
    required = set(required_interfaces)
    if not required:
        raise ValueError("V4_NEW_BUILD_INTERFACES_REQUIRED")
    live_interfaces: set[str] = set()
    all_interfaces: set[str] = set()
    for capability in existing_capabilities:
        capability.validate()
        all_interfaces.update(capability.interfaces)
        if capability.state.upper() in LIVEISH_STATES:
            live_interfaces.update(capability.interfaces)
    live_coverage = len(required & live_interfaces) / len(required)
    any_coverage = len(required & all_interfaces) / len(required)
    relevant_weights = [signal.demand_weight for signal in future_signals if required & set(signal.required_interfaces)]
    demand = max(relevant_weights, default=0.0)
    if live_coverage >= NEW_BUILD_EXISTING_COVERAGE_CEILING:
        decision = BuildDecision.REUSE_OR_EXTEND
        reasons = ("EXISTING_LIVE_CAPABILITY_COVERAGE_SUFFICIENT", "ANTI_BLOAT_REUSE_FIRST")
    elif any_coverage >= NEW_BUILD_EXISTING_COVERAGE_CEILING:
        decision = BuildDecision.COMPOSE_EXISTING
        reasons = ("EXISTING_CAPABILITY_SET_COVERS_REQUIREMENT", "QUALIFY_OR_COMPOSE_BEFORE_NEW_BUILD")
    elif demand < NEW_BUILD_MIN_DEMAND:
        decision = BuildDecision.HOLD_INSUFFICIENT_DEMAND
        reasons = ("FUTURE_DEMAND_BELOW_INVESTMENT_THRESHOLD",)
    else:
        decision = BuildDecision.CANDIDATE_NEW_CAPABILITY
        reasons = ("UNIQUE_UNCOVERED_CAPABILITY_GAP", "FUTURE_DEMAND_JUSTIFIES_SHADOW_INVESTMENT")
    body = {
        "required": sorted(required),
        "live_coverage": round(live_coverage, 9),
        "any_coverage": round(any_coverage, 9),
        "future_demand": round(demand, 9),
        "decision": decision.value,
        "reasons": reasons,
    }
    return BuildGateDecision(decision, round(live_coverage, 9), round(demand, 9), reasons, _receipt(body))


def anticipatory_mutation_gate(
    *,
    improvement_id: str,
    baseline_score: float,
    candidate_score: float,
    hard_regression: bool,
    independent_reproduction: bool,
    rollback_verified: bool,
    authority_change: bool = False,
    owner_approved: bool = False,
) -> MutationGateDecision:
    candidate = ImprovementCandidate(
        improvement_id=improvement_id,
        baseline_score=baseline_score,
        candidate_score=candidate_score,
        hard_regression=hard_regression,
        independent_reproduction=independent_reproduction,
        rollback_verified=rollback_verified,
        authority_change=authority_change,
        owner_approved=owner_approved,
    )
    admitted, blockers, inherited_receipt = RecursiveImprovementGate().evaluate(candidate)
    decision = MutationDecision.CANDIDATE_SHADOW_EVOLUTION if admitted else MutationDecision.HOLD
    body = {
        "candidate": asdict(candidate),
        "fci_receipt": inherited_receipt,
        "decision": decision.value,
        "blockers": blockers,
        "stable_self_promotion_allowed": False,
        "external_effect_authorized": False,
    }
    return MutationGateDecision(decision, blockers, False, False, _receipt(body))


def compile_v4_decision(
    *,
    source_head_sha: str,
    observation: PrimeObservation,
    strategies: Sequence[StrategyCandidate],
    capabilities: Sequence[CapabilitySignal],
    utilization: Sequence[CapabilityUseObservation],
    future_demand: Sequence[DemandSignal],
    demand_slots: int = 8,
) -> V4DecisionIR:
    source = _validate_sha(source_head_sha, label="V4_SOURCE_HEAD_SHA")
    prime: PrimeDecisionIR = compile_prime_decision(observation, strategies)
    utilization_receipt = capability_utilization_court(utilization)
    selected_demand = select_future_demand(future_demand, slots=demand_slots)
    pressure = interface_pressure(selected_demand)
    opportunities = capability_opportunities(capabilities, selected_demand, pressure)
    compositions = composition_search(capabilities, selected_demand)
    consequential = any(signal.external_effect for signal in selected_demand)
    uncertainty = max((signal.uncertainty for signal in selected_demand), default=0.2)
    dependency = max((signal.dependency_centrality for signal in selected_demand), default=0.2)
    consequence = max((signal.value for signal in selected_demand), default=0.2)
    horizon_depth = HorizonOmega().adaptive_depth(
        consequential=consequential,
        consequence=consequence,
        uncertainty=uncertainty,
        dependency_density=dependency,
        adversarial_complexity=max(observation.graph.evidence_conflict, observation.meta_state.novelty),
        requested_depth=max(4, prime.horizon_depth),
    )
    actions: list[str] = []
    if not utilization_receipt.terminality_allowed:
        actions.append("REPAIR_CAPABILITY_UNDERUSE_BEFORE_TERMINALITY")
    for opportunity in opportunities:
        action = opportunity.recommended_action
        if action == CapabilityAction.ROUTER_CHALLENGE:
            actions.append(f"RUN_CLEAN_SLATE_ROUTER_CHALLENGE:{opportunity.capability_id}")
        elif action == CapabilityAction.STRENGTHEN_EXISTING_OWNER:
            actions.append(f"STRENGTHEN_EXISTING_CAPABILITY_OWNER:{opportunity.capability_id}")
        elif action == CapabilityAction.SHADOW_INVESTMENT:
            actions.append(f"OPEN_BOUNDED_SHADOW_QUALIFICATION:{opportunity.capability_id}")
        elif action == CapabilityAction.RETIREMENT_COURT:
            actions.append(f"RUN_NONDESTRUCTIVE_RETIREMENT_COURT:{opportunity.capability_id}")
        elif action == CapabilityAction.HOLD_PROVIDER:
            actions.append(f"PRESERVE_PROVIDER_AUTHORITY_HOLD:{opportunity.capability_id}")
    if compositions:
        best = compositions[0]
        actions.append(f"SHADOW_TEST_CAPABILITY_COMPOSITION:{best.capability_ids[0]}+{best.capability_ids[1]}")
    if not selected_demand:
        actions.append("PRESERVE_CURRENT_CAPABILITY_ECOLOGY_NO_FUTURE_SIGNAL")
    actions = sorted(set(actions))
    mode = V4Mode.SHADOW_ONLY if utilization_receipt.terminality_allowed else V4Mode.HOLD_CAPABILITY_UNDERUSE
    proof_requirements = (
        "CURRENT_SIGNED_SOURCE_IDENTITY",
        "CAPABILITY_UTILIZATION_RECEIPT",
        "FUTURE_DEMAND_EVIDENCE_CLASS_AND_FRESHNESS",
        "INDEPENDENT_SEMANTIC_READBACK_FOR_ANY_LIVE_PROMOTION",
        "VALUE_FOUNDRY_OWNER_VALUE_FOR_OPERATIONAL_PROMOTION",
        "ROLLBACK_AND_INDEPENDENT_REPRODUCTION_FOR_POLICY_EVOLUTION",
        "PROVIDER_NATIVE_READBACK_FOR_ANY_PROVIDER_EFFECT",
    )
    truth_boundary = (
        "V4_IS_NON_SOVEREIGN_COMPOSITION_OVER_PRIME_FCI_SOE_HORIZON_AND_CAPABILITY_MARKET",
        "FORECASTS_AND_DEMAND_SIGNALS_ARE_HYPOTHESES_NOT_FACTS",
        "CAPABILITY_FITNESS_IS_DECISION_SUPPORT_NOT_AUTHORITY",
        "UNDERUSE_MAY_BLOCK_TERMINALITY_BUT_CANNOT_CREATE_PROVIDER_AUTHORITY",
        "NO_PROVIDER_EFFECT_OR_STABLE_SELF_PROMOTION",
        "NO_NEW_SCHEDULER_MEMORY_ROOT_PROOF_PLANE_OR_PROVIDER_EXECUTOR",
    )
    body = {
        "schema": SCHEMA,
        "mode": mode.value,
        "source_head_sha": source,
        "mission_id": observation.mission_id,
        "prime_v1_receipt_sha256": prime.receipt_sha256,
        "utilization_receipt": asdict(utilization_receipt),
        "selected_demand_ids": [item.demand_id for item in selected_demand],
        "interface_pressure": pressure,
        "capability_opportunities": [asdict(item) for item in opportunities],
        "composition_candidates": [asdict(item) for item in compositions],
        "horizon_depth": horizon_depth,
        "preparatory_actions": actions,
        "owner_interrupt_required": prime.owner_interrupt_required,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "stable_self_promotion_allowed": False,
        "proof_requirements": proof_requirements,
        "truth_boundary": truth_boundary,
    }
    return V4DecisionIR(
        schema=SCHEMA,
        mode=mode,
        source_head_sha=source,
        mission_id=observation.mission_id,
        prime_v1_receipt_sha256=prime.receipt_sha256,
        utilization_receipt=utilization_receipt,
        selected_demand_ids=tuple(item.demand_id for item in selected_demand),
        interface_pressure=pressure,
        capability_opportunities=opportunities,
        composition_candidates=compositions,
        horizon_depth=horizon_depth,
        preparatory_actions=tuple(actions),
        owner_interrupt_required=prime.owner_interrupt_required,
        dispatch_authorized=False,
        external_effect_authorized=False,
        stable_self_promotion_allowed=False,
        proof_requirements=proof_requirements,
        truth_boundary=truth_boundary,
        receipt_sha256=_receipt(body),
    )


def v4_capability_manifest() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "composition": {
            "meta_executive": "benchmarking.cfbe_omega.bco_prime_meta_executive_v1",
            "institutional_cognition": "formation_omega.institutional_cognition",
            "strategic_objective_ecology": "formation_omega.strategic_ecology",
            "adaptive_foresight": "ao_harmonic_v3.horizon",
            "capability_market": "alpha_omega_v30.capability_market",
            "owner_value": "benchmarking.cfbe_omega.value_foundry_v1",
        },
        "new_schedulers": 0,
        "new_memory_roots": 0,
        "new_provider_executors": 0,
        "new_authority_planes": 0,
        "new_proof_planes": 0,
        "v4_provider_effect_authority": False,
        "v4_stable_self_promotion": False,
        "forecast_truth_class": "HYPOTHESIS_ONLY",
    }


__all__ = [
    "BuildDecision",
    "BuildGateDecision",
    "CapabilityAction",
    "CapabilityOpportunity",
    "CapabilitySignal",
    "CapabilityUseObservation",
    "CapabilityUtilizationReceipt",
    "CompositionCandidate",
    "DemandSignal",
    "MutationDecision",
    "MutationGateDecision",
    "V4DecisionIR",
    "V4Mode",
    "anticipatory_mutation_gate",
    "capability_opportunities",
    "capability_utilization_court",
    "compile_v4_decision",
    "composition_search",
    "interface_pressure",
    "new_capability_build_gate",
    "select_future_demand",
    "v4_capability_manifest",
]
