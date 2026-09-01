from __future__ import annotations

"""BCOmega PRIME reflexive meta-executive facade v1.

BCOmega PRIME is a non-sovereign composition layer over admitted Bubbles-CFBE
Omega primitives. It observes machine-readable mission/control state, challenges
the current operating method, compiles a bounded meta-decision, and emits shadow
control deltas. It does not replace the CFBE scheduler, Bubbles execution,
MissionIR, DurableMissionRuntime, ProofOS, or any provider authority plane.

v1 is SHADOW_ONLY: it can rank strategies, select adaptive topology, activate the
minimum necessary meta-faculties, compile multi-path continuity lane specs, and
evaluate promotion evidence. It cannot directly dispatch provider effects or
self-promote stable policy.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import (
    AutonomyLevel,
    MetaAction,
    MetaCognitiveState,
    autonomy_gate,
    metacognitive_assessment,
    owner_escalation_gate,
    reflection_gate,
    self_modification_gate,
)
from bubbles.chat_governor_omega3.continuity import (
    ContinuityLaneSpec,
    EffectClass,
    PathRole,
)
from formation_omega.reconciliation_fabric_v2 import (
    AdaptiveTopologyCompiler,
    TaskGraphProfile,
    TopologyMode,
)


SCHEMA = "BCO_PRIME_META_EXECUTIVE_V1"
PROMOTION_MIN_PAIRED_CASES = 30
PROMOTION_MIN_QUALITY_DELTA = 0.02


class PrimeMode(str, Enum):
    SHADOW_ONLY = "SHADOW_ONLY"
    CANDIDATE_BOUNDED_TOPOLOGY_CONTROL = "CANDIDATE_BOUNDED_TOPOLOGY_CONTROL"
    HOLD = "HOLD"


class MetaFaculty(str, Enum):
    OBJECTIVE_GUARDIAN = "OBJECTIVE_GUARDIAN"
    COHERENCE_GUARDIAN = "COHERENCE_GUARDIAN"
    META_COGNITIVE_CRITIC = "META_COGNITIVE_CRITIC"
    FOREST_MIND = "FOREST_MIND"
    HORIZON_MIND = "HORIZON_MIND"
    OMEGA_SCIENTIST = "OMEGA_SCIENTIST"
    ADVERSARIAL_TWIN = "ADVERSARIAL_TWIN"
    CAUSAL_TWIN = "CAUSAL_TWIN"
    ARCHITECTURE_CRITIC = "ARCHITECTURE_CRITIC"
    CAPABILITY_ECONOMIST = "CAPABILITY_ECONOMIST"
    STREAM_GOVERNOR = "STREAM_GOVERNOR"
    EVIDENCE_STRATEGIST = "EVIDENCE_STRATEGIST"
    FAILURE_SCIENTIST = "FAILURE_SCIENTIST"
    OWNER_BURDEN_GOVERNOR = "OWNER_BURDEN_GOVERNOR"
    TERMINALITY_JUDGE = "TERMINALITY_JUDGE"
    VALUE_JUDGE = "VALUE_JUDGE"
    EVOLUTION_GOVERNOR = "EVOLUTION_GOVERNOR"


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    strategy_id: str
    failure_domain: str
    expected_quality: float
    evidence_strength: float
    reliability: float
    reversibility: float
    information_gain: float
    failure_domain_diversity: float
    latency_cost: float
    monetary_cost: float
    owner_burden: float
    risk: float
    external_effect: bool = False
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "StrategyCandidate":
        if not self.strategy_id.strip():
            raise ValueError("STRATEGY_ID_REQUIRED")
        if not self.failure_domain.strip():
            raise ValueError("STRATEGY_FAILURE_DOMAIN_REQUIRED")
        for field_name in (
            "expected_quality",
            "evidence_strength",
            "reliability",
            "reversibility",
            "information_gain",
            "failure_domain_diversity",
            "latency_cost",
            "monetary_cost",
            "owner_burden",
            "risk",
        ):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"STRATEGY_{field_name.upper()}_OUT_OF_RANGE")
        return self

    def fitness(self) -> float:
        self.validate()
        benefit = (
            0.24 * self.expected_quality
            + 0.18 * self.evidence_strength
            + 0.17 * self.reliability
            + 0.10 * self.reversibility
            + 0.12 * self.information_gain
            + 0.08 * self.failure_domain_diversity
        )
        burden = (
            0.04 * self.latency_cost
            + 0.02 * self.monetary_cost
            + 0.03 * self.owner_burden
            + 0.08 * self.risk
        )
        if self.external_effect:
            burden += 0.05
        return round(benefit - burden, 9)


@dataclass(frozen=True, slots=True)
class StrategyTournamentResult:
    champion_strategy_id: str
    challenger_strategy_ids: tuple[str, ...]
    fallback_strategy_id: str | None
    ranked_strategy_ids: tuple[str, ...]
    fitness_by_strategy: tuple[tuple[str, float], ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrimeObservation:
    mission_id: str
    objective_sha256: str
    graph: TaskGraphProfile
    meta_state: MetaCognitiveState
    effect_class: str
    reversible: bool
    exact_authority: bool
    provider_runtime_available: bool
    owner_approval_required: bool = False
    active_streams: int = 1
    shared_write_pressure: float = 0.0
    owner_burden: float = 0.0
    architecture_overlap: float = 0.0
    frontier_gap: float = 0.0
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> "PrimeObservation":
        if not self.mission_id.strip():
            raise ValueError("PRIME_MISSION_ID_REQUIRED")
        digest = self.objective_sha256.strip().lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("PRIME_OBJECTIVE_SHA256_INVALID")
        self.graph.validate()
        if self.active_streams < 0:
            raise ValueError("PRIME_ACTIVE_STREAMS_INVALID")
        for name in ("shared_write_pressure", "owner_burden", "architecture_overlap", "frontier_gap"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"PRIME_{name.upper()}_OUT_OF_RANGE")
        effect = self.effect_class.strip().upper()
        if effect not in {"NO_EFFECT", "READ_ONLY", "PRIVATE_REVERSIBLE", "CONSEQUENTIAL"}:
            raise ValueError("PRIME_EFFECT_CLASS_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class ContextBudget:
    hot_ratio: float
    warm_ratio: float
    cold_ratio: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrimeDecisionIR:
    schema: str
    mode: PrimeMode
    mission_id: str
    objective_sha256: str
    meta_action: MetaAction
    autonomy_level: AutonomyLevel
    topology_mode: TopologyMode
    max_parallel_lanes: int
    max_streams_per_wave: int
    serialize_external_effects: bool
    active_faculties: tuple[MetaFaculty, ...]
    champion_strategy_id: str
    challenger_strategy_ids: tuple[str, ...]
    fallback_strategy_id: str | None
    horizon_depth: int
    context_budget: ContextBudget
    control_actions: tuple[str, ...]
    owner_interrupt_required: bool
    provider_runtime_hold: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    proof_requirements: tuple[str, ...]
    truth_boundary: tuple[str, ...]
    reason_codes: tuple[str, ...]
    receipt_sha256: str

    def canonical_mapping(self, *, include_receipt: bool = True) -> dict[str, object]:
        body = asdict(self)
        if not include_receipt:
            body.pop("receipt_sha256", None)
        return body


@dataclass(frozen=True, slots=True)
class PrimePromotionDecision:
    mode: PrimeMode
    bounded_topology_control_allowed: bool
    external_effect_control_allowed: bool
    stable_self_promotion_allowed: bool
    reason_codes: tuple[str, ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _receipt(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def rank_strategies(candidates: Sequence[StrategyCandidate]) -> StrategyTournamentResult:
    if not candidates:
        raise ValueError("PRIME_STRATEGY_CANDIDATE_REQUIRED")
    ids = [candidate.strategy_id.strip() for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("PRIME_DUPLICATE_STRATEGY_ID")
    validated = [candidate.validate() for candidate in candidates]
    ranked = sorted(validated, key=lambda item: (-item.fitness(), item.strategy_id))
    champion = ranked[0]
    challengers = tuple(item.strategy_id for item in ranked[1:3])
    fallback = next(
        (item.strategy_id for item in ranked[1:] if item.failure_domain != champion.failure_domain),
        ranked[1].strategy_id if len(ranked) > 1 else None,
    )
    reasons = ["FITNESS_WEIGHTED_STRATEGY_TOURNAMENT"]
    if fallback is not None:
        reasons.append("FALLBACK_PRESERVED")
    if any(item.failure_domain != champion.failure_domain for item in ranked[1:]):
        reasons.append("FAILURE_DOMAIN_DIVERSITY_PRESERVED")
    return StrategyTournamentResult(
        champion.strategy_id,
        challengers,
        fallback,
        tuple(item.strategy_id for item in ranked),
        tuple((item.strategy_id, item.fitness()) for item in ranked),
        tuple(reasons),
    )


def _active_faculties(
    observation: PrimeObservation,
    *,
    meta_action: MetaAction,
    topology_mode: TopologyMode,
) -> tuple[MetaFaculty, ...]:
    faculties: set[MetaFaculty] = {
        MetaFaculty.OBJECTIVE_GUARDIAN,
        MetaFaculty.COHERENCE_GUARDIAN,
        MetaFaculty.META_COGNITIVE_CRITIC,
        MetaFaculty.TERMINALITY_JUDGE,
        MetaFaculty.VALUE_JUDGE,
    }
    state = observation.meta_state
    graph = observation.graph
    if topology_mode in {TopologyMode.PARALLEL_CELLS, TopologyMode.HYBRID, TopologyMode.BUILDER_FALSIFIER_WITNESS}:
        faculties.update({MetaFaculty.STREAM_GOVERNOR, MetaFaculty.CAPABILITY_ECONOMIST})
    if meta_action in {MetaAction.CHALLENGE, MetaAction.REFLECT, MetaAction.REPLAN}:
        faculties.update({MetaFaculty.OMEGA_SCIENTIST, MetaFaculty.ADVERSARIAL_TWIN})
    if meta_action == MetaAction.ROLLBACK or state.repeated_failure_count:
        faculties.add(MetaFaculty.FAILURE_SCIENTIST)
    if meta_action == MetaAction.SEEK_EVIDENCE or state.evidence_coverage < 0.65:
        faculties.add(MetaFaculty.EVIDENCE_STRATEGIST)
    if state.novelty >= 0.50 or graph.uncertainty >= 0.50:
        faculties.update({MetaFaculty.CAUSAL_TWIN, MetaFaculty.HORIZON_MIND})
    if graph.node_count >= 12 or observation.active_streams >= 4:
        faculties.add(MetaFaculty.FOREST_MIND)
    if observation.owner_burden >= 0.35:
        faculties.add(MetaFaculty.OWNER_BURDEN_GOVERNOR)
    if observation.architecture_overlap >= 0.35:
        faculties.add(MetaFaculty.ARCHITECTURE_CRITIC)
    if observation.frontier_gap >= 0.35:
        faculties.add(MetaFaculty.EVOLUTION_GOVERNOR)
    return tuple(sorted(faculties, key=lambda item: item.value))


def _horizon_depth(observation: PrimeObservation) -> int:
    pressure = max(
        observation.meta_state.novelty,
        observation.graph.uncertainty,
        observation.graph.evidence_conflict,
        observation.graph.consequential_fraction,
        observation.frontier_gap,
    )
    if pressure >= 0.75:
        return 50
    if pressure >= 0.55:
        return 25
    if pressure >= 0.30:
        return 10
    return 5


def _context_budget(observation: PrimeObservation) -> ContextBudget:
    pressure = observation.meta_state.resource_pressure
    freshness = observation.meta_state.context_freshness
    if pressure >= 0.80:
        return ContextBudget(0.30, 0.30, 0.40, ("RESOURCE_PRESSURE_HIGH_COMPRESS_HOT_CONTEXT",))
    if freshness < 0.45:
        return ContextBudget(0.50, 0.35, 0.15, ("CONTEXT_FRESHNESS_LOW_REFRESH_HOT_WARM",))
    if observation.graph.node_count >= 20:
        return ContextBudget(0.40, 0.35, 0.25, ("LARGE_GRAPH_CONTEXT_VIRTUALIZATION",))
    return ContextBudget(0.55, 0.30, 0.15, ("NORMAL_CONTEXT_BUDGET",))


def _parallel_budget(observation: PrimeObservation, topology_parallel: int) -> tuple[int, int, tuple[str, ...]]:
    max_parallel = max(1, int(topology_parallel))
    reasons: list[str] = []
    if observation.shared_write_pressure >= 0.70:
        max_parallel = min(max_parallel, 2)
        reasons.append("SHARED_WRITE_PRESSURE_THROTTLES_PARALLELISM")
    if observation.meta_state.resource_pressure >= 0.85:
        max_parallel = min(max_parallel, 2)
        reasons.append("RESOURCE_PRESSURE_THROTTLES_PARALLELISM")
    if observation.effect_class.strip().upper() == "CONSEQUENTIAL":
        reasons.append("CONSEQUENTIAL_EFFECT_LANE_SERIALIZED")
    stream_budget = max(1, min(max_parallel, 4))
    if observation.active_streams > stream_budget:
        reasons.append("ACTIVE_STREAM_WIP_EXCEEDS_WAVE_BUDGET")
    if not reasons:
        reasons.append("TOPOLOGY_PARALLEL_BUDGET_ACCEPTED")
    return max_parallel, stream_budget, tuple(reasons)


def _control_actions(observation: PrimeObservation, meta_action: MetaAction, *, max_streams: int) -> tuple[str, ...]:
    actions = {
        MetaAction.CONTINUE: ["PRESERVE_CURRENT_STRATEGY"],
        MetaAction.REFLECT: ["RUN_BOUNDED_REFLECTION"],
        MetaAction.SEEK_EVIDENCE: ["COMMISSION_MINIMUM_TARGETED_EVIDENCE"],
        MetaAction.REPLAN: ["COMPILE_ALTERNATE_TOPOLOGY"],
        MetaAction.CHALLENGE: ["RUN_ADVERSARIAL_STRATEGY_TOURNAMENT"],
        MetaAction.ROLLBACK: ["RESTORE_LAST_VERIFIED_META_POLICY"],
    }[meta_action]
    if observation.architecture_overlap >= 0.35:
        actions.append("CONSOLIDATE_BEFORE_NEW_ARCHITECTURE")
    if observation.owner_burden >= 0.35:
        actions.append("BATCH_OWNER_DECISIONS_AND_REDUCE_INTERRUPTS")
    if observation.meta_state.resource_pressure >= 0.80:
        actions.append("COMPRESS_CONTEXT_AND_DEFER_COLD_STATE")
    if observation.active_streams > max_streams:
        actions.append("THROTTLE_STREAM_WIP_WITH_FAIRNESS")
    if observation.shared_write_pressure < 0.35 and observation.graph.ready_parallel_count >= 3:
        actions.append("EXPAND_INDEPENDENT_SAFE_PARALLEL_LANES")
    return tuple(actions)


def compile_prime_decision(
    observation: PrimeObservation,
    strategies: Sequence[StrategyCandidate],
) -> PrimeDecisionIR:
    observation.validate()
    tournament = rank_strategies(strategies)
    topology = AdaptiveTopologyCompiler().compile(observation.graph)
    meta = metacognitive_assessment(observation.meta_state)
    autonomy = autonomy_gate(
        effect_class=observation.effect_class,
        reversible=observation.reversible,
        exact_authority=observation.exact_authority,
        provider_runtime_available=observation.provider_runtime_available,
        evidence_coverage=observation.meta_state.evidence_coverage,
        owner_approval_required=observation.owner_approval_required,
    )
    trigger_present = meta.action != MetaAction.CONTINUE
    expected_gain = min(
        1.0,
        0.35 * observation.graph.uncertainty
        + 0.30 * observation.graph.evidence_conflict
        + 0.20 * observation.meta_state.novelty
        + 0.15 * min(1.0, observation.meta_state.repeated_failure_count / 3.0),
    )
    reflection = reflection_gate(
        trigger_present=trigger_present,
        expected_decision_gain=expected_gain,
        estimated_reflection_cost=0.10 + 0.25 * observation.meta_state.resource_pressure,
    )
    max_parallel, max_streams, parallel_reasons = _parallel_budget(observation, topology.max_parallel)
    faculties = _active_faculties(observation, meta_action=meta.action, topology_mode=topology.mode)
    provider_hold = autonomy.level == AutonomyLevel.HOLD_PROVIDER_RUNTIME
    safe_routes = sum(1 for item in strategies if not item.external_effect)
    owner_escalation = owner_escalation_gate(
        safe_routes_remaining=safe_routes,
        exact_owner_decision_required=autonomy.level == AutonomyLevel.HOLD_OWNER_TRIGGER,
        provider_only_gate=provider_hold,
        safety_or_legal_gate=False,
    )
    proof_requirements = [
        "CURRENT_SOURCE_IDENTITY",
        "META_DECISION_RECEIPT",
        "INDEPENDENT_SEMANTIC_READBACK",
        "ROLLBACK_OR_SAFE_NO_EFFECT",
        "PAIRED_SHADOW_COMPARISON_BEFORE_LIVE_META_CONTROL",
        "OBSERVED_OWNER_VALUE_BEFORE_STABLE_PROMOTION",
    ]
    if provider_hold or observation.effect_class.strip().upper() in {"PRIVATE_REVERSIBLE", "CONSEQUENTIAL"}:
        proof_requirements.append("PROVIDER_RUNTIME_AND_ACTION_SPECIFIC_READBACK")
    reasons = list(topology.reason_codes)
    reasons.extend(meta.reasons)
    reasons.extend(tournament.reason_codes)
    reasons.extend(parallel_reasons)
    reasons.append("BOUNDED_REFLECTION_SELECTED" if reflection.run_reflection else "REFLECTION_NOT_VALUE_JUSTIFIED")
    if provider_hold:
        reasons.append("PROVIDER_RUNTIME_HELD")
    if owner_escalation.interrupt_owner:
        reasons.append("EXACT_OWNER_TRIGGER_REQUIRED")
    context_budget = _context_budget(observation)
    control_actions = _control_actions(observation, meta.action, max_streams=max_streams)
    draft = {
        "schema": SCHEMA,
        "mode": PrimeMode.SHADOW_ONLY.value,
        "mission_id": observation.mission_id,
        "objective_sha256": observation.objective_sha256.lower(),
        "meta_action": meta.action.value,
        "autonomy_level": autonomy.level.value,
        "topology_mode": topology.mode.value,
        "max_parallel_lanes": max_parallel,
        "max_streams_per_wave": max_streams,
        "serialize_external_effects": True,
        "active_faculties": tuple(item.value for item in faculties),
        "champion_strategy_id": tournament.champion_strategy_id,
        "challenger_strategy_ids": tournament.challenger_strategy_ids,
        "fallback_strategy_id": tournament.fallback_strategy_id,
        "horizon_depth": _horizon_depth(observation),
        "context_budget": asdict(context_budget),
        "control_actions": control_actions,
        "owner_interrupt_required": owner_escalation.interrupt_owner,
        "provider_runtime_hold": provider_hold,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "proof_requirements": tuple(sorted(set(proof_requirements))),
        "truth_boundary": (
            "shadow_meta_control_does_not_replace_cfbe_scheduler_or_bubbles_execution",
            "meta_state_is_machine_observable_control_metadata_not_private_chain_of_thought",
            "strategy_fitness_is_decision_support_not_truth_or_provider_authority",
            "horizon_depth_is_conditional_planning_not_prediction_certainty",
            "external_effects_remain_serialized_and_separately_authorized",
            "bco_prime_cannot_self_promote_stable_policy",
        ),
        "reason_codes": tuple(sorted(set(reasons))),
    }
    receipt_hash = _receipt(draft)
    return PrimeDecisionIR(
        schema=SCHEMA,
        mode=PrimeMode.SHADOW_ONLY,
        mission_id=observation.mission_id,
        objective_sha256=observation.objective_sha256.lower(),
        meta_action=meta.action,
        autonomy_level=autonomy.level,
        topology_mode=topology.mode,
        max_parallel_lanes=max_parallel,
        max_streams_per_wave=max_streams,
        serialize_external_effects=True,
        active_faculties=faculties,
        champion_strategy_id=tournament.champion_strategy_id,
        challenger_strategy_ids=tournament.challenger_strategy_ids,
        fallback_strategy_id=tournament.fallback_strategy_id,
        horizon_depth=draft["horizon_depth"],
        context_budget=context_budget,
        control_actions=control_actions,
        owner_interrupt_required=owner_escalation.interrupt_owner,
        provider_runtime_hold=provider_hold,
        dispatch_authorized=False,
        external_effect_authorized=False,
        proof_requirements=draft["proof_requirements"],
        truth_boundary=draft["truth_boundary"],
        reason_codes=draft["reason_codes"],
        receipt_sha256=receipt_hash,
    )


def compile_continuity_lanes(
    *,
    decision: PrimeDecisionIR,
    command_id: str,
    strategies: Sequence[StrategyCandidate],
    checkpoint_ref: str = "",
) -> tuple[ContinuityLaneSpec, ...]:
    """Compile shadow multi-path lanes without mutating the continuity database."""
    if decision.mode != PrimeMode.SHADOW_ONLY:
        raise ValueError("PRIME_V1_EXPECTS_SHADOW_DECISION")
    by_id = {item.strategy_id: item.validate() for item in strategies}
    if decision.champion_strategy_id not in by_id:
        raise ValueError("PRIME_CHAMPION_NOT_IN_STRATEGIES")
    roles: dict[str, PathRole] = {decision.champion_strategy_id: PathRole.PRIMARY}
    if decision.fallback_strategy_id:
        roles[decision.fallback_strategy_id] = PathRole.FALLBACK
    for strategy_id in decision.challenger_strategy_ids:
        roles.setdefault(strategy_id, PathRole.CHALLENGER)
    ordered_ids = [decision.champion_strategy_id]
    ordered_ids.extend(item for item in decision.challenger_strategy_ids if item not in ordered_ids)
    if decision.fallback_strategy_id and decision.fallback_strategy_id not in ordered_ids:
        ordered_ids.append(decision.fallback_strategy_id)
    lanes: list[ContinuityLaneSpec] = []
    for index, strategy_id in enumerate(ordered_ids):
        item = by_id[strategy_id]
        effect = EffectClass.HIGH_CONSEQUENCE if item.external_effect else EffectClass.NO_EFFECT
        concurrency_group = "external-effect-serialized" if item.external_effect else ""
        lanes.append(
            ContinuityLaneSpec(
                lane_id=f"{command_id}:prime:{index + 1}:{strategy_id}",
                command_id=command_id,
                mission_id=decision.mission_id,
                path_id=strategy_id,
                path_role=roles[strategy_id],
                concurrency_group=concurrency_group,
                effect_class=effect,
                checkpoint_ref=checkpoint_ref,
                priority_delta=10.0 if roles[strategy_id] == PathRole.PRIMARY else 0.0,
            )
        )
    return tuple(lanes)


def prime_promotion_gate(
    *,
    baseline_quality: float,
    candidate_quality: float,
    paired_cases: int,
    hard_regressions: int,
    rollback_available: bool,
    independent_verifier_pass: bool,
    observed_owner_value_positive: bool,
    hosted_shadow_pass: bool,
    provider_runtime_required: bool = False,
    provider_runtime_proven: bool = False,
) -> PrimePromotionDecision:
    """Evaluate only bounded topology-control candidacy; never provider effects."""
    inherited = self_modification_gate(
        baseline_score=baseline_quality,
        candidate_score=candidate_quality,
        paired_cases=paired_cases,
        hard_regressions=hard_regressions,
        rollback_available=rollback_available,
        independent_verifier_pass=independent_verifier_pass,
        observed_value_positive=observed_owner_value_positive,
    )
    reasons = [f"SELF_MOD:{inherited.state}"]
    delta = candidate_quality - baseline_quality
    if hard_regressions:
        return PrimePromotionDecision(PrimeMode.HOLD, False, False, False, tuple(reasons + ["HARD_REGRESSION"]))
    if not hosted_shadow_pass:
        return PrimePromotionDecision(PrimeMode.HOLD, False, False, False, tuple(reasons + ["HOSTED_SHADOW_REQUIRED"]))
    if paired_cases < PROMOTION_MIN_PAIRED_CASES:
        return PrimePromotionDecision(PrimeMode.HOLD, False, False, False, tuple(reasons + ["THIRTY_PAIRED_CASES_REQUIRED"]))
    if delta < PROMOTION_MIN_QUALITY_DELTA:
        return PrimePromotionDecision(PrimeMode.HOLD, False, False, False, tuple(reasons + ["MINIMUM_QUALITY_UPLIFT_NOT_MET"]))
    if not rollback_available or not independent_verifier_pass or not observed_owner_value_positive:
        return PrimePromotionDecision(PrimeMode.HOLD, False, False, False, tuple(reasons + ["ROLLBACK_VERIFIER_VALUE_REQUIRED"]))
    if provider_runtime_required and not provider_runtime_proven:
        return PrimePromotionDecision(PrimeMode.HOLD, False, False, False, tuple(reasons + ["PROVIDER_RUNTIME_PROOF_REQUIRED"]))
    if inherited.state != "CANDIDATE_STABLE_REVIEW":
        return PrimePromotionDecision(PrimeMode.HOLD, False, False, False, tuple(reasons + ["INHERITED_SELF_MOD_GATE_NOT_READY"]))
    return PrimePromotionDecision(
        PrimeMode.CANDIDATE_BOUNDED_TOPOLOGY_CONTROL,
        True,
        False,
        False,
        tuple(reasons + ["BOUNDED_TOPOLOGY_CONTROL_CANDIDATE_ONLY"]),
    )


def prime_capability_manifest() -> Mapping[str, object]:
    return {
        "schema": SCHEMA,
        "composition": (
            "CFBE_AUTOPILOT_METACOGNITION_V1",
            "FORMATION_OMEGA_ADAPTIVE_TOPOLOGY",
            "BUBBLES_CFBE_MULTISTREAM_CONTINUITY_V1",
            "DURABLE_MISSION_RUNTIME_V1_REFERENCE",
            "FAILURE_WIN_BEHAVIORAL_CONVERGENCE_REFERENCE",
            "PROOFOS_AND_OWNER_VALUE_REFERENCE",
        ),
        "new_authority_planes": 0,
        "new_schedulers": 0,
        "new_memory_roots": 0,
        "new_provider_executors": 0,
        "v1_live_effect_authority": False,
        "v1_mode": PrimeMode.SHADOW_ONLY.value,
        "capability_fabric": "BCO_PRIME_CAPABILITY_FABRIC_V1",
        "zero_manual_capability_functions": 100,
        "capability_fabric_external_effect_authority": False,
    }
