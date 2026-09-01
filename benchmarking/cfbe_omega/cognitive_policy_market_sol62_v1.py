from __future__ import annotations

"""Cognitive Policy Market + Counterfactual Twin + SOL 6.2 bridge v1.

The dependency is intentionally asymmetric. PRIME/CFBE may observe SOL state and
propose policy. SOL 6.2 never imports this module and remains independently
operable. This module cannot dispatch, consume authority, or perform provider
effects; it can only compile evidence-bearing policy recommendations and a
constitutional admission verdict.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import (
    PrimeDecisionIR,
    StrategyCandidate,
)
from sol_61_runtime.sol_62 import Sol62Runtime


SCHEMA = "CFBE_COGNITIVE_POLICY_MARKET_SOL62_V1"
MIN_ROBUST_SCORE = 0.35
MIN_EVIDENCE_COVERAGE = 0.45
DIVERSITY_TRIGGER_UNCERTAINTY = 0.55
DIVERSITY_TRIGGER_CONTRADICTION = 0.55


class PolicySource(str, Enum):
    BCO_PRIME = "BCO_PRIME"
    CFBE = "CFBE"
    FOREST_MIND = "FOREST_MIND"
    HORIZON_MIND = "HORIZON_MIND"
    OMEGA_SCIENTIST = "OMEGA_SCIENTIST"
    ADVERSARIAL_TWIN = "ADVERSARIAL_TWIN"
    CAUSAL_TWIN = "CAUSAL_TWIN"
    HUMAN_OWNER = "HUMAN_OWNER"


class AdmissionVerdict(str, Enum):
    ACCEPT = "ACCEPT"
    CONSTRAIN = "CONSTRAIN"
    DEFER = "DEFER"
    REJECT = "REJECT"
    SEEK_EVIDENCE = "SEEK_EVIDENCE"
    OWNER_REQUIRED = "OWNER_REQUIRED"


@dataclass(frozen=True, slots=True)
class SolObservationEnvelope:
    mission_id: str
    objective_sha256: str
    mission_status: str
    target_state_sha256: str
    observed_state_sha256: str
    open_transition_ids: tuple[str, ...]
    verified_transition_ids: tuple[str, ...]
    consequential_open_count: int
    provider_runtime_available: bool
    exact_authority_available: bool
    owner_approval_required: bool
    evidence_coverage: float
    uncertainty: float
    contradiction_pressure: float
    resource_pressure: float
    owner_burden: float
    active_streams: int
    source_version: str
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "SolObservationEnvelope":
        if not self.mission_id.strip():
            raise ValueError("POLICY_MARKET_MISSION_ID_REQUIRED")
        for name in ("objective_sha256", "target_state_sha256", "observed_state_sha256"):
            value = str(getattr(self, name)).strip().lower()
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError(f"POLICY_MARKET_{name.upper()}_INVALID")
        for name in (
            "evidence_coverage",
            "uncertainty",
            "contradiction_pressure",
            "resource_pressure",
            "owner_burden",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"POLICY_MARKET_{name.upper()}_OUT_OF_RANGE")
        if self.active_streams < 0 or self.consequential_open_count < 0:
            raise ValueError("POLICY_MARKET_NEGATIVE_COUNT")
        if not self.source_version.strip():
            raise ValueError("POLICY_MARKET_SOURCE_VERSION_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class PolicyProposal:
    proposal_id: str
    proposer: PolicySource
    mission_id: str
    objective_sha256: str
    strategy_id: str
    intended_transition_ids: tuple[str, ...]
    control_actions: tuple[str, ...]
    expected_quality: float
    confidence: float
    evidence_strength: float
    reliability: float
    reversibility: float
    information_gain: float
    failure_domain_diversity: float
    latency_cost: float
    monetary_cost: float
    owner_burden: float
    risk: float
    external_effect: bool
    requires_provider_runtime: bool
    requires_owner_approval: bool
    assumptions: tuple[str, ...] = ()
    proof_requirements: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "PolicyProposal":
        if not self.proposal_id.strip() or not self.strategy_id.strip() or not self.mission_id.strip():
            raise ValueError("POLICY_PROPOSAL_IDENTITY_REQUIRED")
        objective = self.objective_sha256.strip().lower()
        if len(objective) != 64 or any(ch not in "0123456789abcdef" for ch in objective):
            raise ValueError("POLICY_OBJECTIVE_SHA256_INVALID")
        for name in (
            "expected_quality",
            "confidence",
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
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"POLICY_{name.upper()}_OUT_OF_RANGE")
        return self

    def base_utility(self) -> float:
        self.validate()
        benefit = (
            0.23 * self.expected_quality
            + 0.14 * self.confidence
            + 0.15 * self.evidence_strength
            + 0.13 * self.reliability
            + 0.08 * self.reversibility
            + 0.09 * self.information_gain
            + 0.06 * self.failure_domain_diversity
        )
        burden = (
            0.03 * self.latency_cost
            + 0.02 * self.monetary_cost
            + 0.03 * self.owner_burden
            + 0.09 * self.risk
        )
        if self.external_effect:
            burden += 0.04
        return round(benefit - burden, 9)


@dataclass(frozen=True, slots=True)
class CounterfactualScenario:
    scenario_id: str
    provider_available: bool = True
    evidence_multiplier: float = 1.0
    resource_multiplier: float = 1.0
    contradiction_multiplier: float = 1.0

    def validate(self) -> "CounterfactualScenario":
        if not self.scenario_id.strip():
            raise ValueError("COUNTERFACTUAL_SCENARIO_ID_REQUIRED")
        for name in ("evidence_multiplier", "resource_multiplier", "contradiction_multiplier"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 2.0:
                raise ValueError(f"COUNTERFACTUAL_{name.upper()}_OUT_OF_RANGE")
        return self


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    proposal_id: str
    scenario_scores: tuple[tuple[str, float], ...]
    mean_score: float
    worst_case_score: float
    failure_count: int
    robust_score: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PolicyMarketDecision:
    schema: str
    mission_id: str
    objective_sha256: str
    champion_proposal_id: str
    challenger_proposal_ids: tuple[str, ...]
    fallback_proposal_id: str | None
    ranked_proposal_ids: tuple[str, ...]
    robust_scores: tuple[tuple[str, float], ...]
    proposer_diversity_count: int
    diversity_required: bool
    diversity_satisfied: bool
    reason_codes: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class SolConstitutionalAdmission:
    schema: str
    mission_id: str
    verdict: AdmissionVerdict
    admitted_proposal_id: str | None
    max_parallel_lanes: int
    serialize_external_effects: bool
    owner_interrupt_required: bool
    provider_runtime_hold: bool
    policy_control_admitted: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    required_actions: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    reason_codes: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class CognitivePolicyCycleReceipt:
    schema: str
    observation_sha256: str
    prime_decision_sha256: str
    policy_market: PolicyMarketDecision
    admission: SolConstitutionalAdmission
    truth_boundary: tuple[str, ...]
    receipt_sha256: str


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    raw = value if isinstance(value, str) else _canonical_json(value)
    return sha256(raw.encode("utf-8")).hexdigest()


def default_counterfactual_scenarios() -> tuple[CounterfactualScenario, ...]:
    return (
        CounterfactualScenario("BASELINE"),
        CounterfactualScenario("PROVIDER_LOSS", provider_available=False),
        CounterfactualScenario("EVIDENCE_SHOCK", evidence_multiplier=0.55),
        CounterfactualScenario("RESOURCE_SPIKE", resource_multiplier=1.65),
        CounterfactualScenario("CONTRADICTION_SURGE", contradiction_multiplier=1.60),
    )


def proposal_from_strategy(
    *,
    observation: SolObservationEnvelope,
    decision: PrimeDecisionIR,
    strategy: StrategyCandidate,
    proposer: PolicySource = PolicySource.BCO_PRIME,
) -> PolicyProposal:
    observation.validate()
    strategy.validate()
    if decision.mission_id != observation.mission_id:
        raise ValueError("PRIME_SOL_MISSION_MISMATCH")
    if decision.objective_sha256.lower() != observation.objective_sha256.lower():
        raise ValueError("PRIME_SOL_OBJECTIVE_MISMATCH")
    proposal_id = f"{proposer.value}:{strategy.strategy_id}:{decision.receipt_sha256[:16]}"
    return PolicyProposal(
        proposal_id=proposal_id,
        proposer=proposer,
        mission_id=observation.mission_id,
        objective_sha256=observation.objective_sha256.lower(),
        strategy_id=strategy.strategy_id,
        intended_transition_ids=tuple(observation.open_transition_ids),
        control_actions=tuple(decision.control_actions),
        expected_quality=float(strategy.expected_quality),
        confidence=round(0.5 * float(strategy.reliability) + 0.5 * float(strategy.evidence_strength), 9),
        evidence_strength=float(strategy.evidence_strength),
        reliability=float(strategy.reliability),
        reversibility=float(strategy.reversibility),
        information_gain=float(strategy.information_gain),
        failure_domain_diversity=float(strategy.failure_domain_diversity),
        latency_cost=float(strategy.latency_cost),
        monetary_cost=float(strategy.monetary_cost),
        owner_burden=max(float(strategy.owner_burden), observation.owner_burden),
        risk=float(strategy.risk),
        external_effect=bool(strategy.external_effect),
        requires_provider_runtime=bool(strategy.external_effect or decision.provider_runtime_hold),
        requires_owner_approval=bool(decision.owner_interrupt_required),
        assumptions=(
            f"PRIME_META_ACTION:{decision.meta_action.value}",
            f"PRIME_TOPOLOGY:{decision.topology_mode.value}",
        ),
        proof_requirements=tuple(decision.proof_requirements),
        proof_refs=tuple(strategy.proof_refs),
    )


def proposals_from_prime(
    *,
    observation: SolObservationEnvelope,
    decision: PrimeDecisionIR,
    strategies: Sequence[StrategyCandidate],
) -> tuple[PolicyProposal, ...]:
    by_id = {item.strategy_id: item for item in strategies}
    selected: list[str] = [decision.champion_strategy_id]
    selected.extend(item for item in decision.challenger_strategy_ids if item not in selected)
    if decision.fallback_strategy_id and decision.fallback_strategy_id not in selected:
        selected.append(decision.fallback_strategy_id)
    missing = [strategy_id for strategy_id in selected if strategy_id not in by_id]
    if missing:
        raise ValueError("PRIME_POLICY_STRATEGY_MISSING:" + ",".join(sorted(missing)))
    return tuple(
        proposal_from_strategy(
            observation=observation,
            decision=decision,
            strategy=by_id[strategy_id],
        )
        for strategy_id in selected
    )


def evaluate_counterfactual(
    proposal: PolicyProposal,
    observation: SolObservationEnvelope,
    *,
    scenarios: Sequence[CounterfactualScenario] | None = None,
) -> CounterfactualResult:
    proposal.validate()
    observation.validate()
    if proposal.mission_id != observation.mission_id:
        raise ValueError("COUNTERFACTUAL_MISSION_MISMATCH")
    if proposal.objective_sha256.lower() != observation.objective_sha256.lower():
        raise ValueError("COUNTERFACTUAL_OBJECTIVE_MISMATCH")
    cases = tuple(scenarios or default_counterfactual_scenarios())
    if not cases:
        raise ValueError("COUNTERFACTUAL_SCENARIOS_REQUIRED")
    scores: list[tuple[str, float]] = []
    reasons: set[str] = set()
    failures = 0
    for scenario in cases:
        scenario.validate()
        evidence = min(1.0, proposal.evidence_strength * scenario.evidence_multiplier)
        resource_penalty = min(
            1.0,
            observation.resource_pressure
            * scenario.resource_multiplier
            * (0.55 * proposal.latency_cost + 0.45 * proposal.owner_burden),
        )
        contradiction_penalty = min(
            1.0,
            observation.contradiction_pressure
            * scenario.contradiction_multiplier
            * (0.50 + 0.50 * proposal.risk),
        )
        provider_penalty = 0.0
        if proposal.requires_provider_runtime and not scenario.provider_available:
            provider_penalty = 0.30
            reasons.add("COUNTERFACTUAL_PROVIDER_LOSS_DEGRADES_POLICY")
        assumption_penalty = min(0.16, 0.02 * len(proposal.assumptions))
        score = (
            proposal.base_utility()
            + 0.10 * evidence
            - 0.12 * resource_penalty
            - 0.15 * contradiction_penalty
            - provider_penalty
            - assumption_penalty
        )
        score = round(max(0.0, min(1.0, score)), 9)
        scores.append((scenario.scenario_id, score))
        if score < MIN_ROBUST_SCORE:
            failures += 1
    values = [score for _, score in scores]
    mean_score = round(sum(values) / len(values), 9)
    worst_case = min(values)
    robust_score = round(0.65 * worst_case + 0.35 * mean_score, 9)
    reasons.add(
        "COUNTERFACTUAL_ALL_SCENARIOS_CLEAR_FLOOR"
        if failures == 0
        else "COUNTERFACTUAL_SCENARIO_FAILURES_PRESENT"
    )
    return CounterfactualResult(
        proposal_id=proposal.proposal_id,
        scenario_scores=tuple(scores),
        mean_score=mean_score,
        worst_case_score=worst_case,
        failure_count=failures,
        robust_score=robust_score,
        reason_codes=tuple(sorted(reasons)),
    )


def run_policy_market(
    *,
    observation: SolObservationEnvelope,
    proposals: Sequence[PolicyProposal],
    scenarios: Sequence[CounterfactualScenario] | None = None,
) -> PolicyMarketDecision:
    observation.validate()
    if not proposals:
        raise ValueError("POLICY_MARKET_PROPOSAL_REQUIRED")
    ids = [item.proposal_id for item in proposals]
    if len(ids) != len(set(ids)):
        raise ValueError("POLICY_MARKET_DUPLICATE_PROPOSAL_ID")
    validated = [item.validate() for item in proposals]
    for item in validated:
        if item.mission_id != observation.mission_id:
            raise ValueError("POLICY_MARKET_MISSION_MISMATCH")
        if item.objective_sha256.lower() != observation.objective_sha256.lower():
            raise ValueError("POLICY_MARKET_OBJECTIVE_MISMATCH")
    results = {
        item.proposal_id: evaluate_counterfactual(item, observation, scenarios=scenarios)
        for item in validated
    }
    ranked = sorted(
        validated,
        key=lambda item: (-results[item.proposal_id].robust_score, -item.base_utility(), item.proposal_id),
    )
    champion = ranked[0]
    challengers = tuple(item.proposal_id for item in ranked[1:3])
    fallback = next(
        (
            item.proposal_id
            for item in ranked[1:]
            if item.proposer != champion.proposer or item.strategy_id != champion.strategy_id
        ),
        ranked[1].proposal_id if len(ranked) > 1 else None,
    )
    proposer_diversity = len({item.proposer for item in ranked})
    diversity_required = (
        observation.uncertainty >= DIVERSITY_TRIGGER_UNCERTAINTY
        or observation.contradiction_pressure >= DIVERSITY_TRIGGER_CONTRADICTION
        or observation.consequential_open_count > 0
        or champion.external_effect
    )
    diversity_satisfied = (not diversity_required) or proposer_diversity >= 2
    reasons = {"COUNTERFACTUAL_POLICY_TOURNAMENT"}
    if fallback:
        reasons.add("POLICY_FALLBACK_PRESERVED")
    if diversity_required:
        reasons.add("INDEPENDENT_PROPOSER_DIVERSITY_REQUIRED")
    reasons.add("PROPOSER_DIVERSITY_SATISFIED" if diversity_satisfied else "PROPOSER_DIVERSITY_MISSING")
    draft = {
        "schema": SCHEMA,
        "mission_id": observation.mission_id,
        "objective_sha256": observation.objective_sha256.lower(),
        "champion_proposal_id": champion.proposal_id,
        "challenger_proposal_ids": challengers,
        "fallback_proposal_id": fallback,
        "ranked_proposal_ids": tuple(item.proposal_id for item in ranked),
        "robust_scores": tuple((item.proposal_id, results[item.proposal_id].robust_score) for item in ranked),
        "proposer_diversity_count": proposer_diversity,
        "diversity_required": diversity_required,
        "diversity_satisfied": diversity_satisfied,
        "reason_codes": tuple(sorted(reasons)),
    }
    return PolicyMarketDecision(receipt_sha256=_digest(draft), **draft)


def constitutional_admission(
    *,
    observation: SolObservationEnvelope,
    market: PolicyMarketDecision,
    proposals: Sequence[PolicyProposal],
    prime_decision: PrimeDecisionIR,
) -> SolConstitutionalAdmission:
    observation.validate()
    by_id = {item.proposal_id: item.validate() for item in proposals}
    if market.champion_proposal_id not in by_id:
        raise ValueError("CONSTITUTIONAL_CHAMPION_MISSING")
    champion = by_id[market.champion_proposal_id]
    robust = float(dict(market.robust_scores)[champion.proposal_id])
    reasons: list[str] = []
    actions: set[str] = set(champion.control_actions)
    proofs = set(champion.proof_requirements)
    verdict = AdmissionVerdict.ACCEPT

    if market.mission_id != observation.mission_id or champion.mission_id != observation.mission_id:
        verdict = AdmissionVerdict.REJECT
        reasons.append("CONSTITUTIONAL_MISSION_MISMATCH")
    elif market.objective_sha256.lower() != observation.objective_sha256.lower():
        verdict = AdmissionVerdict.REJECT
        reasons.append("CONSTITUTIONAL_OBJECTIVE_MISMATCH")
    elif observation.mission_status == "VERIFIED_REALITY":
        verdict = AdmissionVerdict.REJECT
        reasons.append("MISSION_ALREADY_VERIFIED_REALITY")
    elif not market.diversity_satisfied:
        verdict = AdmissionVerdict.SEEK_EVIDENCE
        reasons.append("INDEPENDENT_CHALLENGER_REQUIRED")
        actions.add("COMMISSION_INDEPENDENT_POLICY_CHALLENGER")
    elif robust < MIN_ROBUST_SCORE:
        verdict = AdmissionVerdict.REJECT
        reasons.append("COUNTERFACTUAL_ROBUSTNESS_BELOW_FLOOR")
    elif observation.evidence_coverage < MIN_EVIDENCE_COVERAGE:
        verdict = AdmissionVerdict.SEEK_EVIDENCE
        reasons.append("EVIDENCE_COVERAGE_BELOW_FLOOR")
        actions.add("COMMISSION_MINIMUM_TARGETED_EVIDENCE")
    elif champion.requires_owner_approval or observation.owner_approval_required:
        verdict = AdmissionVerdict.OWNER_REQUIRED
        reasons.append("EXACT_OWNER_DECISION_REQUIRED")
    elif champion.external_effect and not observation.exact_authority_available:
        verdict = AdmissionVerdict.DEFER
        reasons.append("EXACT_EFFECT_AUTHORITY_UNAVAILABLE")
    elif champion.requires_provider_runtime and not observation.provider_runtime_available:
        verdict = AdmissionVerdict.DEFER
        reasons.append("PROVIDER_RUNTIME_UNAVAILABLE")
    elif prime_decision.provider_runtime_hold:
        verdict = AdmissionVerdict.DEFER
        reasons.append("PRIME_PROVIDER_RUNTIME_HOLD_PRESERVED")
    elif observation.contradiction_pressure >= 0.75:
        verdict = AdmissionVerdict.CONSTRAIN
        reasons.append("HIGH_CONTRADICTION_CONSTRAINS_CONTROL")
        actions.add("RUN_ADVERSARIAL_VALIDATION_BEFORE_EXECUTION")
        proofs.add("CONTRADICTION_RESOLUTION_PROOF")
    elif observation.resource_pressure >= 0.85 or observation.owner_burden >= 0.60:
        verdict = AdmissionVerdict.CONSTRAIN
        if observation.resource_pressure >= 0.85:
            reasons.append("RESOURCE_PRESSURE_CONSTRAINS_PARALLELISM")
            actions.add("THROTTLE_STREAM_WIP_WITH_FAIRNESS")
        if observation.owner_burden >= 0.60:
            reasons.append("OWNER_BURDEN_CONSTRAINS_INTERRUPT_RATE")
            actions.add("BATCH_OWNER_DECISIONS_AND_REDUCE_INTERRUPTS")
    else:
        reasons.append("POLICY_CONSTITUTIONALLY_ADMISSIBLE")

    max_parallel = max(1, int(prime_decision.max_parallel_lanes))
    if verdict in {AdmissionVerdict.CONSTRAIN, AdmissionVerdict.OWNER_REQUIRED}:
        max_parallel = min(max_parallel, 2)
    if champion.external_effect or observation.consequential_open_count:
        max_parallel = 1
        actions.add("SERIALIZE_CONSEQUENTIAL_EFFECT_LANE")

    policy_control_admitted = verdict in {AdmissionVerdict.ACCEPT, AdmissionVerdict.CONSTRAIN}
    owner_interrupt = verdict == AdmissionVerdict.OWNER_REQUIRED
    provider_hold = verdict == AdmissionVerdict.DEFER and (
        champion.requires_provider_runtime or prime_decision.provider_runtime_hold
    )
    proofs.update(
        {
            "SOL_TARGET_STATE_CONTRACT",
            "SOL_PROOF_CONTRACT",
            "POLICY_MARKET_RECEIPT",
            "COUNTERFACTUAL_TWIN_RECEIPT",
        }
    )
    draft = {
        "schema": SCHEMA,
        "mission_id": observation.mission_id,
        "verdict": verdict.value,
        "admitted_proposal_id": champion.proposal_id if policy_control_admitted else None,
        "max_parallel_lanes": max_parallel,
        "serialize_external_effects": True,
        "owner_interrupt_required": owner_interrupt,
        "provider_runtime_hold": provider_hold,
        "policy_control_admitted": policy_control_admitted,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "required_actions": tuple(sorted(actions)),
        "proof_requirements": tuple(sorted(proofs)),
        "reason_codes": tuple(sorted(set(reasons))),
    }
    return SolConstitutionalAdmission(
        schema=SCHEMA,
        mission_id=observation.mission_id,
        verdict=verdict,
        admitted_proposal_id=draft["admitted_proposal_id"],
        max_parallel_lanes=max_parallel,
        serialize_external_effects=True,
        owner_interrupt_required=owner_interrupt,
        provider_runtime_hold=provider_hold,
        policy_control_admitted=policy_control_admitted,
        dispatch_authorized=False,
        external_effect_authorized=False,
        required_actions=draft["required_actions"],
        proof_requirements=draft["proof_requirements"],
        reason_codes=draft["reason_codes"],
        receipt_sha256=_digest(draft),
    )


def capture_sol_observation(
    runtime: Sol62Runtime,
    mission_id: str,
    *,
    provider_runtime_available: bool,
    exact_authority_available: bool,
    owner_approval_required: bool,
    evidence_coverage: float,
    uncertainty: float,
    contradiction_pressure: float,
    resource_pressure: float,
    owner_burden: float,
    active_streams: int,
    source_version: str,
    proof_refs: Sequence[str] = (),
) -> SolObservationEnvelope:
    mission = runtime.control.get_state("sol62.mission", mission_id)
    if not mission:
        raise KeyError(mission_id)
    mission_status = runtime.control.get_state("sol62.mission_status", mission_id)
    observed = runtime.mission_state(mission_id)["value"]
    transitions = {
        row["key"]: row["value"]
        for row in runtime._rows("sol62.transition")
        if row["value"].get("mission_id") == mission_id
    }
    statuses = {row["key"]: row["value"] for row in runtime._rows("sol62.transition_status")}
    open_ids: list[str] = []
    verified_ids: list[str] = []
    consequential_open_count = 0
    for transition_id, body in transitions.items():
        state = str((statuses.get(transition_id) or {}).get("status") or "UNKNOWN")
        if state == "VERIFIED":
            verified_ids.append(transition_id)
        elif state not in {"SUPERSEDED", "CANCELLED"}:
            open_ids.append(transition_id)
            if bool(body.get("consequential")):
                consequential_open_count += 1
    spec = mission["value"]
    status_value = (mission_status or {}).get("value", {})
    return SolObservationEnvelope(
        mission_id=mission_id,
        objective_sha256=_digest(str(spec["objective"])),
        mission_status=str(status_value.get("status") or "OPEN"),
        target_state_sha256=_digest(spec["target_state"]),
        observed_state_sha256=_digest(observed),
        open_transition_ids=tuple(sorted(open_ids)),
        verified_transition_ids=tuple(sorted(verified_ids)),
        consequential_open_count=consequential_open_count,
        provider_runtime_available=bool(provider_runtime_available),
        exact_authority_available=bool(exact_authority_available),
        owner_approval_required=bool(owner_approval_required),
        evidence_coverage=float(evidence_coverage),
        uncertainty=float(uncertainty),
        contradiction_pressure=float(contradiction_pressure),
        resource_pressure=float(resource_pressure),
        owner_burden=float(owner_burden),
        active_streams=int(active_streams),
        source_version=source_version,
        proof_refs=tuple(proof_refs),
    ).validate()


def compile_cognitive_policy_cycle(
    *,
    observation: SolObservationEnvelope,
    prime_decision: PrimeDecisionIR,
    prime_strategies: Sequence[StrategyCandidate],
    independent_proposals: Sequence[PolicyProposal] = (),
    scenarios: Sequence[CounterfactualScenario] | None = None,
) -> CognitivePolicyCycleReceipt:
    observation.validate()
    prime_proposals = proposals_from_prime(
        observation=observation,
        decision=prime_decision,
        strategies=prime_strategies,
    )
    proposals = tuple(prime_proposals) + tuple(independent_proposals)
    market = run_policy_market(observation=observation, proposals=proposals, scenarios=scenarios)
    admission = constitutional_admission(
        observation=observation,
        market=market,
        proposals=proposals,
        prime_decision=prime_decision,
    )
    truth_boundary = (
        "cognitive_policy_market_proposes_and_challenges_but_never_dispatches",
        "sol62_remains_independently_operable_without_this_module",
        "constitutional_admission_is_policy_admission_not_effect_authority",
        "counterfactual_scores_are_decision_support_not_observed_provider_truth",
        "provider_effect_authority_requires_sol62_fencing_and_exact_action_authority",
        "stable_policy_promotion_requires_separate_empirical_value_and_regression_proof",
        "meta_control_metadata_is_machine_observable_and_not_private_chain_of_thought",
    )
    draft = {
        "schema": SCHEMA,
        "observation_sha256": _digest(asdict(observation)),
        "prime_decision_sha256": prime_decision.receipt_sha256,
        "policy_market": asdict(market),
        "admission": asdict(admission),
        "truth_boundary": truth_boundary,
    }
    return CognitivePolicyCycleReceipt(
        schema=SCHEMA,
        observation_sha256=draft["observation_sha256"],
        prime_decision_sha256=prime_decision.receipt_sha256,
        policy_market=market,
        admission=admission,
        truth_boundary=truth_boundary,
        receipt_sha256=_digest(draft),
    )


def cognitive_policy_market_manifest() -> Mapping[str, object]:
    return {
        "schema": SCHEMA,
        "role": "ASYMMETRIC_META_CONTROL_AND_CONSTITUTIONAL_ADMISSION",
        "depends_on": ("BCO_PRIME_META_EXECUTIVE_V1", "CFBE", "SOL62"),
        "sol62_imports_policy_market": False,
        "policy_market_may_observe_sol62": True,
        "new_schedulers": 0,
        "new_memory_roots": 0,
        "new_provider_executors": 0,
        "new_authority_planes": 0,
        "dispatch_authority": False,
        "external_effect_authority": False,
        "stable_self_promotion": False,
    }
