from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


BENCHMARK_WEIGHTS: Mapping[str, float] = {
    "legal_route": 0.15,
    "evidence_integrity": 0.20,
    "authority_quality": 0.15,
    "fact_chronology": 0.10,
    "contradiction_reasoning": 0.10,
    "adversarial_resilience": 0.10,
    "remedy_procedure": 0.10,
    "uncertainty_calibration": 0.05,
    "traceability": 0.05,
}

FATAL_FAILURES = frozenset(
    {
        "FABRICATED_AUTHORITY",
        "FABRICATED_FACT",
        "FABRICATED_QUOTATION",
        "WRONG_FORUM_WHERE_MATERIAL",
        "NONEXISTENT_CAUSE_OF_ACTION",
        "MATERIAL_EVIDENCE_IGNORED",
        "ANSWER_KEY_LEAK",
        "PRIVATE_CASE_CROSS_CONTAMINATION",
        "BINDING_AUTHORITY_IGNORED",
        "REMEDY_FORUM_MISMATCH",
        "INFERENCE_PRESENTED_AS_PROVED_FACT",
        "FALSE_CLAIM_OF_COMPLETENESS",
    }
)


@dataclass(frozen=True)
class BenchmarkEvaluation:
    score: float
    decision: str
    fatal_failures: tuple[str, ...]
    missing_metrics: tuple[str, ...]


@dataclass(frozen=True)
class CandidatePromotionDecision:
    decision: str
    reasons: tuple[str, ...]
    promotion_state: str


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def evaluate_benchmark(
    competency_scores: Mapping[str, float],
    *,
    fatal_events: Sequence[str] = (),
) -> BenchmarkEvaluation:
    fatals = tuple(sorted(set(fatal_events) & FATAL_FAILURES))
    missing = tuple(sorted(set(BENCHMARK_WEIGHTS) - set(competency_scores)))
    weighted = sum(
        BENCHMARK_WEIGHTS[name] * _clamp(competency_scores.get(name, 0.0))
        for name in BENCHMARK_WEIGHTS
    )
    decision = "FAIL_FATAL" if fatals else ("PASS" if not missing and weighted >= 0.80 else "FAIL")
    return BenchmarkEvaluation(
        score=round(weighted, 8),
        decision=decision,
        fatal_failures=fatals,
        missing_metrics=missing,
    )


def evaluate_candidate_promotion(
    *,
    original_failure_repaired: bool,
    fatal_regressions: Sequence[str],
    supported_case_count: int,
    mutation_passed: bool,
    red_team_passed: bool,
    current_law_verified: bool,
    rollback_available: bool,
    independently_replicated: bool,
    global_regression_passed: bool,
) -> CandidatePromotionDecision:
    reasons: list[str] = []
    fatal = sorted(set(fatal_regressions) & FATAL_FAILURES)
    if not original_failure_repaired:
        reasons.append("ORIGINAL_FAILURE_NOT_REPAIRED")
    if fatal:
        reasons.append("FATAL_REGRESSION:" + ",".join(fatal))
    if supported_case_count < 2:
        reasons.append("INSUFFICIENT_CROSS_CASE_SUPPORT")
    if not mutation_passed:
        reasons.append("ADVERSARIAL_MUTATION_FAILED")
    if not red_team_passed:
        reasons.append("RED_TEAM_FAILED")
    if not current_law_verified:
        reasons.append("CURRENT_LAW_NOT_VERIFIED")
    if not rollback_available:
        reasons.append("ROLLBACK_NOT_AVAILABLE")
    if not independently_replicated:
        reasons.append("INDEPENDENT_REPLICATION_MISSING")
    if not global_regression_passed:
        reasons.append("GLOBAL_REGRESSION_FAILED")

    if reasons:
        return CandidatePromotionDecision("REJECT", tuple(reasons), "CANDIDATE")
    return CandidatePromotionDecision("ACCEPT", (), "SHADOW_VALIDATED")


def select_next_case(candidates: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Choose the highest-information weakness-driven benchmark case."""
    if not candidates:
        raise ValueError("at least one candidate case is required")

    weights = {
        "weakness_score": 0.30,
        "legal_materiality": 0.20,
        "failure_recurrence": 0.15,
        "domain_undercoverage": 0.15,
        "authority_change_risk": 0.10,
        "real_world_frequency": 0.10,
    }

    def priority(case: Mapping[str, Any]) -> float:
        return sum(weights[key] * _clamp(case.get(key, 0.0)) for key in weights)

    return max(candidates, key=priority)


def to_evolution_metrics(
    evaluation: BenchmarkEvaluation,
    competency_scores: Mapping[str, float],
    *,
    security: float = 1.0,
    reversibility: float = 1.0,
    recovery: float = 0.8,
    reuse: float = 0.8,
    owner_burden_reduction: float = 0.7,
    cost_efficiency: float = 0.7,
) -> dict[str, float]:
    """Map CASEFORGE results into the existing EvidenceOps EvolutionGovernor."""
    evidence = _clamp(competency_scores.get("evidence_integrity", 0.0))
    facts = _clamp(competency_scores.get("fact_chronology", 0.0))
    uncertainty = _clamp(competency_scores.get("uncertainty_calibration", 0.0))
    traceability = _clamp(competency_scores.get("traceability", 0.0))
    contradiction = _clamp(competency_scores.get("contradiction_reasoning", 0.0))
    return {
        "factual_accuracy": (evidence + facts + uncertainty) / 3.0,
        "proof_completeness": (evidence + traceability) / 2.0,
        "security": _clamp(security),
        "reversibility": _clamp(reversibility),
        "completion_rate": _clamp(evaluation.score),
        "contradiction_detection": contradiction,
        "recovery": _clamp(recovery),
        "reuse": _clamp(reuse),
        "owner_burden_reduction": _clamp(owner_burden_reduction),
        "cost_efficiency": _clamp(cost_efficiency),
    }
