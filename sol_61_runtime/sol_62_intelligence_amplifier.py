from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Mapping, Sequence

SCHEMA = "SOL62_INTELLIGENCE_AMPLIFIER_V1"
VERSION = "2.0.0"


class ReasoningMode(str, Enum):
    DIRECT = "DIRECT"
    DELIBERATE = "DELIBERATE"
    SEARCH = "SEARCH"
    SCIENTIFIC = "SCIENTIFIC"
    ADVERSARIAL = "ADVERSARIAL"


@dataclass(frozen=True, slots=True)
class CognitionProfile:
    complexity: float = 0.5
    stakes: float = 0.5
    uncertainty: float = 0.5
    novelty: float = 0.5
    evidence_gap: float = 0.5
    time_pressure: float = 0.0
    reversibility: float = 1.0
    multi_domain: bool = False

    def __post_init__(self) -> None:
        for name in (
            "complexity", "stakes", "uncertainty", "novelty",
            "evidence_gap", "time_pressure", "reversibility",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    strategy_id: str
    family: str
    mechanisms: tuple[str, ...]
    fit: float
    information_gain: float
    reliability: float
    cost: float
    latency: float

    def score(self, risk: float) -> float:
        return round(
            0.34 * self.fit
            + 0.30 * self.information_gain
            + 0.25 * self.reliability
            + 0.11 * risk
            - 0.06 * self.cost
            - 0.04 * self.latency,
            8,
        )


@dataclass(frozen=True, slots=True)
class IntelligencePlan:
    plan_id: str
    mode: ReasoningMode
    reasoning_budget: int
    max_parallel_strategies: int
    selected_strategies: tuple[StrategyCandidate, ...]
    required_checks: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    uncertainty_reporting_required: bool = True
    independent_verifier_required: bool = False
    chain_of_thought_exposure_allowed: bool = False
    authority_expansion: bool = False
    provider_effect_authorized: bool = False
    goal_mutation_allowed: bool = False
    truth_root_replacement_allowed: bool = False


def _pressure(p: CognitionProfile) -> float:
    irreversibility = 1.0 - p.reversibility
    return min(1.0, max(0.0,
        0.22 * p.complexity
        + 0.20 * p.stakes
        + 0.18 * p.uncertainty
        + 0.14 * p.novelty
        + 0.14 * p.evidence_gap
        + 0.08 * irreversibility
        + 0.04 * float(p.multi_domain)
    ))


def _mode(pressure: float, p: CognitionProfile) -> ReasoningMode:
    if p.stakes >= 0.80 and (p.evidence_gap >= 0.55 or p.reversibility <= 0.35):
        return ReasoningMode.ADVERSARIAL
    if p.uncertainty >= 0.75 and p.evidence_gap >= 0.60:
        return ReasoningMode.SCIENTIFIC
    if pressure >= 0.67 or p.complexity >= 0.80:
        return ReasoningMode.SEARCH
    if pressure >= 0.38:
        return ReasoningMode.DELIBERATE
    return ReasoningMode.DIRECT


def _budget(pressure: float, p: CognitionProfile) -> int:
    base = 1 + round(9 * pressure)
    compressed = max(1, base - round(3 * p.time_pressure))
    proof_floor = 6 if p.stakes >= 0.80 or p.reversibility <= 0.20 else 1
    return max(proof_floor, min(10, compressed))


def _candidates(p: CognitionProfile) -> tuple[StrategyCandidate, ...]:
    irreversible = 1.0 - p.reversibility
    return (
        StrategyCandidate(
            "PLAN_SEARCH", "SEARCH",
            ("Tree/Graph search", "MCTS/UCT", "LPA*/D* Lite"),
            min(1.0, .45*p.complexity + .35*p.novelty + .20*float(p.multi_domain)),
            min(1.0, .45*p.uncertainty + .35*p.novelty + .20*p.evidence_gap),
            .82, .55, .60,
        ),
        StrategyCandidate(
            "CAUSAL_FALSIFICATION", "CAUSAL",
            ("FCI/NOTEARS", "counterfactual testing", "BOCPD/ADWIN"),
            min(1.0, .35*p.uncertainty + .35*p.evidence_gap + .30*p.stakes),
            min(1.0, .50*p.evidence_gap + .30*p.uncertainty + .20*p.novelty),
            .88, .58, .58,
        ),
        StrategyCandidate(
            "RETRIEVAL_SYNTHESIS", "KNOWLEDGE",
            ("HNSW", "RRF", "ColBERT-style reranking"),
            min(1.0, .55*p.evidence_gap + .25*float(p.multi_domain) + .20*p.novelty),
            min(1.0, .60*p.evidence_gap + .25*p.uncertainty + .15*p.novelty),
            .90, .42, .38,
        ),
        StrategyCandidate(
            "EXPERIMENT_OPTIMIZE", "OPTIMIZATION",
            ("Bayesian Optimization", "Thompson Sampling", "Hyperband/BOHB"),
            min(1.0, .40*p.novelty + .35*p.complexity + .25*p.uncertainty),
            min(1.0, .45*p.uncertainty + .35*p.novelty + .20*p.evidence_gap),
            .80, .68, .70,
        ),
        StrategyCandidate(
            "ADVERSARIAL_PROOF", "PROOF",
            ("QuickXplain", "Delta Debugging", "CEGAR/CEGIS", "Conformal Prediction"),
            min(1.0, .40*p.stakes + .30*irreversible + .30*p.evidence_gap),
            min(1.0, .45*p.stakes + .30*p.evidence_gap + .25*irreversible),
            .95, .62, .62,
        ),
    )


def compile_intelligence_plan(
    profile: CognitionProfile,
    *,
    available_families: Sequence[str] | None = None,
    max_parallel: int = 3,
) -> IntelligencePlan:
    if max_parallel < 1:
        raise ValueError("max_parallel must be positive")

    pressure = _pressure(profile)
    mode = _mode(pressure, profile)
    budget = _budget(pressure, profile)
    allowed = {x.upper() for x in available_families} if available_families else None
    risk = max(profile.stakes, 1.0 - profile.reversibility, profile.uncertainty)
    ranked = sorted(
        (c for c in _candidates(profile) if allowed is None or c.family.upper() in allowed),
        key=lambda c: (-c.score(risk), c.strategy_id),
    )
    parallel = min(max_parallel, 1 if mode is ReasoningMode.DIRECT else 2 if mode is ReasoningMode.DELIBERATE else 3)

    selected: list[StrategyCandidate] = []
    families: set[str] = set()
    for candidate in ranked:
        if candidate.family in families:
            continue
        selected.append(candidate)
        families.add(candidate.family)
        if len(selected) >= parallel:
            break

    high_assurance = profile.stakes >= 0.80 or profile.reversibility <= 0.20
    if high_assurance and all(x.strategy_id != "ADVERSARIAL_PROOF" for x in selected):
        proof = next((x for x in ranked if x.strategy_id == "ADVERSARIAL_PROOF"), None)
        if proof is not None:
            if len(selected) >= parallel:
                selected[-1] = proof
            else:
                selected.append(proof)

    checks = [
        "FRESH_EVIDENCE_OR_CURRENTNESS_CHECK",
        "ALTERNATIVE_HYPOTHESIS_OR_ROUTE",
        "CONTRADICTION_SCAN",
        "UNCERTAINTY_CALIBRATION",
        "COUNTERFACTUAL_OR_FALSIFIER",
        "PROOF_BEFORE_PROMOTION",
        "VALUE_OF_INFORMATION_NEXT_ACTION",
        "EVIDENCE_DIVERSITY_CONFIDENCE_CAP",
    ]
    if profile.multi_domain:
        checks.append("CROSS_DOMAIN_CONSISTENCY")
    if profile.complexity >= 0.65 or profile.uncertainty >= 0.65:
        checks.extend(("ROBUSTNESS_SENSITIVITY_GATE", "STAGNATION_MUTATION_GUARD"))
    if high_assurance:
        checks.extend(("INDEPENDENT_VERIFIER", "FAIL_CLOSED_ON_AMBIGUITY"))

    fingerprint = {
        "profile": asdict(profile),
        "mode": mode.value,
        "budget": budget,
        "strategies": [x.strategy_id for x in selected],
        "checks": checks,
    }
    plan_id = "IA-" + hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]

    return IntelligencePlan(
        plan_id=plan_id,
        mode=mode,
        reasoning_budget=budget,
        max_parallel_strategies=parallel,
        selected_strategies=tuple(selected),
        required_checks=tuple(checks),
        stop_conditions=(
            "TARGET_DECISION_HAS_CURRENT_EVIDENCE",
            "NO_MATERIAL_UNRESOLVED_CONTRADICTION",
            "MARGINAL_INFORMATION_GAIN_BELOW_THRESHOLD",
            "BUDGET_OR_DEADLINE_REACHED_WITH_UNCERTAINTY_REPORTED",
            "REQUIRED_PROOF_PREDICATES_SATISFIED_OR_EXPLICITLY_HELD",
        ),
        independent_verifier_required=high_assurance,
    )


def module_summary() -> Mapping[str, object]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "adaptive_reasoning": True,
        "parallel_hypothesis_families": True,
        "causal_falsification": True,
        "uncertainty_calibration": True,
        "adversarial_proof": True,
        "value_of_information": True,
        "hypothesis_tournament": True,
        "robustness_sensitivity_gate": True,
        "stagnation_mutation_guard": True,
        "confidence_calibration": True,
        "external_algorithm_cohort": "HG-EXTALG-001..100",
        "authority_expansion": False,
        "provider_effect_authorized": False,
        "goal_mutation_allowed": False,
        "truth_root_replacement_allowed": False,
        "chain_of_thought_exposure_allowed": False,
    }


# ---- v2 metacognitive residuals ---------------------------------------------

@dataclass(frozen=True, slots=True)
class EvidenceSignal:
    signal_id: str
    hypothesis_id: str
    direction: str
    source_domain: str
    reliability: float
    independence: float
    currentness: float

    def __post_init__(self) -> None:
        if self.direction not in {"SUPPORT", "CONTRADICT"}:
            raise ValueError("direction must be SUPPORT or CONTRADICT")
        for name in ("reliability", "independence", "currentness"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Hypothesis:
    hypothesis_id: str
    prior_score: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.prior_score) <= 1.0:
            raise ValueError("prior_score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class HypothesisAssessment:
    hypothesis_id: str
    evidence_score: float
    support_mass: float
    contradiction_mass: float
    independent_domains: int
    confidence_cap: float
    unresolved_contradiction: bool


def assess_hypotheses(
    hypotheses: Sequence[Hypothesis],
    evidence: Sequence[EvidenceSignal],
) -> tuple[HypothesisAssessment, ...]:
    """Evidence-weighted tournament; scores are decision aids, not probabilities."""
    out: list[HypothesisAssessment] = []
    for hypothesis in hypotheses:
        relevant = [e for e in evidence if e.hypothesis_id == hypothesis.hypothesis_id]
        support = sum(
            e.reliability * e.independence * e.currentness
            for e in relevant if e.direction == "SUPPORT"
        )
        contradict = sum(
            e.reliability * e.independence * e.currentness
            for e in relevant if e.direction == "CONTRADICT"
        )
        domains = {e.source_domain for e in relevant if e.source_domain}
        diversity = min(1.0, len(domains) / 3.0)
        score = max(0.0, min(1.0, hypothesis.prior_score + 0.18 * (support - contradict)))
        contradiction_ratio = contradict / max(1e-9, support + contradict)
        cap = min(0.98, 0.60 + 0.30 * diversity + 0.08 * min(1.0, support / 2.0))
        cap *= max(0.35, 1.0 - 0.65 * contradiction_ratio)
        score = min(score, cap)
        out.append(HypothesisAssessment(
            hypothesis_id=hypothesis.hypothesis_id,
            evidence_score=round(score, 8),
            support_mass=round(support, 8),
            contradiction_mass=round(contradict, 8),
            independent_domains=len(domains),
            confidence_cap=round(cap, 8),
            unresolved_contradiction=contradict >= 0.25,
        ))
    return tuple(sorted(out, key=lambda x: (-x.evidence_score, x.hypothesis_id)))


@dataclass(frozen=True, slots=True)
class InvestigationAction:
    action_id: str
    expected_information_gain: float
    discrimination_power: float
    reversibility: float
    cost: float
    latency: float
    risk: float

    def __post_init__(self) -> None:
        for name in (
            "expected_information_gain", "discrimination_power",
            "reversibility", "cost", "latency", "risk",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    def value_of_information_score(self) -> float:
        return round(
            0.43 * self.expected_information_gain
            + 0.29 * self.discrimination_power
            + 0.13 * self.reversibility
            - 0.06 * self.cost
            - 0.05 * self.latency
            - 0.04 * self.risk,
            8,
        )


@dataclass(frozen=True, slots=True)
class InvestigationDecision:
    action_id: str | None
    score: float
    continue_investigation: bool
    reason: str


def choose_next_investigation(
    actions: Sequence[InvestigationAction],
    *,
    minimum_information_gain: float = 0.08,
) -> InvestigationDecision:
    if not actions:
        return InvestigationDecision(None, 0.0, False, "NO_CANDIDATE_INVESTIGATION")
    ranked = sorted(actions, key=lambda a: (-a.value_of_information_score(), a.action_id))
    best = ranked[0]
    if best.expected_information_gain < minimum_information_gain:
        return InvestigationDecision(
            None,
            best.value_of_information_score(),
            False,
            "MARGINAL_INFORMATION_GAIN_BELOW_THRESHOLD",
        )
    return InvestigationDecision(
        best.action_id,
        best.value_of_information_score(),
        True,
        "HIGHEST_VALUE_OF_INFORMATION",
    )


@dataclass(frozen=True, slots=True)
class DecisionOption:
    option_id: str
    expected_value: float
    uncertainty: float
    downside: float
    reversibility: float

    def __post_init__(self) -> None:
        for name in ("expected_value", "uncertainty", "downside", "reversibility"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class RobustDecision:
    selected_option_id: str | None
    margin: float
    stable: bool
    scores: Mapping[str, float]
    reason: str


def robust_choice(
    options: Sequence[DecisionOption],
    *,
    perturbation: float = 0.10,
    minimum_margin: float = 0.06,
) -> RobustDecision:
    if not options:
        return RobustDecision(None, 0.0, False, {}, "NO_OPTIONS")
    if not 0.0 <= perturbation <= 1.0:
        raise ValueError("perturbation must be between 0 and 1")
    scores: dict[str, float] = {}
    for option in options:
        score = (
            option.expected_value
            - (0.55 + perturbation) * option.uncertainty
            - (0.35 + 0.5 * perturbation) * option.downside
            + 0.15 * option.reversibility
        )
        scores[option.option_id] = round(score, 8)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) == 1:
        return RobustDecision(ranked[0][0], 1.0, True, scores, "SINGLE_OPTION")
    margin = ranked[0][1] - ranked[1][1]
    stable = margin >= minimum_margin
    return RobustDecision(
        ranked[0][0] if stable else None,
        round(margin, 8),
        stable,
        scores,
        "ROBUST_MARGIN_PASS" if stable else "FRAGILE_WINNER_HOLD",
    )


@dataclass(frozen=True, slots=True)
class AttemptTrace:
    strategy_family: str
    outcome_fingerprint: str
    information_gain: float
    materially_changed: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.information_gain) <= 1.0:
            raise ValueError("information_gain must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class StagnationDecision:
    stagnating: bool
    change_strategy_required: bool
    reason: str


def detect_stagnation(
    attempts: Sequence[AttemptTrace],
    *,
    window: int = 3,
    information_gain_floor: float = 0.04,
) -> StagnationDecision:
    if window < 2:
        raise ValueError("window must be at least 2")
    if len(attempts) < window:
        return StagnationDecision(False, False, "INSUFFICIENT_HISTORY")
    recent = list(attempts[-window:])
    same_family = len({a.strategy_family for a in recent}) == 1
    same_outcome = len({a.outcome_fingerprint for a in recent}) == 1
    low_gain = all(a.information_gain <= information_gain_floor for a in recent)
    no_change = not any(a.materially_changed for a in recent)
    stagnating = no_change and ((same_family and low_gain) or same_outcome)
    return StagnationDecision(
        stagnating,
        stagnating,
        "CHANGED_MECHANISM_REQUIRED" if stagnating else "CONTINUE_CURRENT_STRATEGY",
    )


def calibrated_confidence(
    raw_confidence: float,
    *,
    independent_domains: int,
    contradiction_mass: float,
    historical_brier: float | None = None,
    calibration_samples: int = 0,
) -> float:
    if not 0.0 <= raw_confidence <= 1.0:
        raise ValueError("raw_confidence must be between 0 and 1")
    if contradiction_mass < 0.0:
        raise ValueError("contradiction_mass cannot be negative")
    diversity_cap = min(0.98, 0.62 + 0.12 * max(0, independent_domains))
    sample_cap = 0.80 if calibration_samples < 20 else 0.92 if calibration_samples < 100 else 0.98
    calibration_cap = 0.98
    if historical_brier is not None:
        if not 0.0 <= historical_brier <= 1.0:
            raise ValueError("historical_brier must be between 0 and 1")
        calibration_cap = max(0.50, 1.0 - 0.75 * historical_brier)
    contradiction_cap = max(0.35, 1.0 - min(0.65, 0.30 * contradiction_mass))
    return round(
        min(raw_confidence, diversity_cap, sample_cap, calibration_cap, contradiction_cap),
        8,
    )
