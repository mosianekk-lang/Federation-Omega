from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Mapping, Sequence

SCHEMA = "SOL62_INTELLIGENCE_AMPLIFIER_V1"
VERSION = "1.0.0"


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
    ]
    if profile.multi_domain:
        checks.append("CROSS_DOMAIN_CONSISTENCY")
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
        "external_algorithm_cohort": "HG-EXTALG-001..100",
        "authority_expansion": False,
        "provider_effect_authorized": False,
        "goal_mutation_allowed": False,
        "truth_root_replacement_allowed": False,
        "chain_of_thought_exposure_allowed": False,
    }
