from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


class EvidenceFreshnessRisk:
    def score(self, age_days: float, freshness_sla_days: float, materiality: float) -> float:
        if age_days < 0 or freshness_sla_days <= 0 or not 0 <= materiality <= 1:
            raise ValueError("invalid freshness inputs")
        overdue = max(0.0, age_days - freshness_sla_days) / freshness_sla_days
        return max(0.0, min(1.0, materiality * (1.0 - 1.0 / (1.0 + overdue))))


@dataclass(frozen=True)
class AssumptionSignal:
    name: str
    sensitivity: float
    uncertainty: float
    evidence_confidence: float


class AssumptionCriticalityRanker:
    def rank(self, assumptions: Iterable[AssumptionSignal]) -> list[tuple[str, float]]:
        scored = []
        for a in assumptions:
            if any(not 0 <= x <= 1 for x in (a.sensitivity, a.uncertainty, a.evidence_confidence)):
                raise ValueError("assumption dimensions must be between 0 and 1")
            score = a.sensitivity * (0.55 * a.uncertainty + 0.45 * (1.0 - a.evidence_confidence))
            scored.append((a.name, score))
        return sorted(scored, key=lambda x: (-x[1], x[0]))


class ThesisDecayIndex:
    def score(self, *, stale_evidence: float, adverse_signals: float, broken_assumptions: float, unresolved_critical: float) -> float:
        xs = (stale_evidence, adverse_signals, broken_assumptions, unresolved_critical)
        if any(not 0 <= x <= 1 for x in xs):
            raise ValueError("all dimensions must be between 0 and 1")
        return min(1.0, 0.18 * stale_evidence + 0.30 * adverse_signals + 0.32 * broken_assumptions + 0.20 * unresolved_critical)


class DealSunkCostBiasGuard:
    def evaluate(self, *, sunk_cost: float, future_expected_value: float, future_required_cost: float, future_risk_cost: float = 0.0) -> dict[str, float | str]:
        if sunk_cost < 0 or future_required_cost < 0 or future_risk_cost < 0:
            raise ValueError("costs cannot be negative")
        continuation_margin = future_expected_value - future_required_cost - future_risk_cost
        return {"sunk_cost_ignored_for_forward_decision": sunk_cost, "continuation_margin": continuation_margin, "decision": "CONTINUE" if continuation_margin > 0 else "STOP_OR_RESTRUCTURE"}


@dataclass(frozen=True)
class InformationQuestion:
    question_id: str
    decision_impact: float
    uncertainty_reduction: float
    probability_resolved: float
    cost: float
    time_penalty: float


class InformationValuePrioritizer:
    def rank(self, questions: Iterable[InformationQuestion]) -> list[tuple[str, float]]:
        result = []
        for q in questions:
            if any(not 0 <= x <= 1 for x in (q.decision_impact, q.uncertainty_reduction, q.probability_resolved, q.cost, q.time_penalty)):
                raise ValueError("information dimensions must be between 0 and 1")
            value = q.decision_impact * q.uncertainty_reduction * q.probability_resolved - 0.45 * q.cost - 0.20 * q.time_penalty
            result.append((q.question_id, value))
        return sorted(result, key=lambda x: (-x[1], x[0]))


@dataclass(frozen=True)
class SynergyItem:
    synergy_id: str
    value: float
    drivers: frozenset[str]
    value_pool: str


class SynergyDoubleCountDetector:
    def detect(self, items: Iterable[SynergyItem], overlap_threshold: float = 0.6) -> list[tuple[str, str, float]]:
        items = list(items)
        flags: list[tuple[str, str, float]] = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a.value_pool != b.value_pool:
                    continue
                union = a.drivers | b.drivers
                overlap = 1.0 if not union else len(a.drivers & b.drivers) / len(union)
                if overlap >= overlap_threshold:
                    flags.append((a.synergy_id, b.synergy_id, overlap))
        return flags


class RegimeSensitivityVector:
    def impact(self, exposures: Mapping[str, float], shocks: Mapping[str, float]) -> dict[str, float]:
        drivers = sorted(set(exposures) | set(shocks))
        contributions = {d: float(exposures.get(d, 0.0)) * float(shocks.get(d, 0.0)) for d in drivers}
        contributions["TOTAL"] = sum(contributions.values())
        return contributions


class NoDealDominanceTest:
    def evaluate(self, deal_risk_adjusted_value: float, no_deal_value: float, alternatives: Iterable[float] = ()) -> dict[str, float | str]:
        best_alt = max([no_deal_value, *list(alternatives)])
        margin = deal_risk_adjusted_value - best_alt
        return {"deal_value": deal_risk_adjusted_value, "best_non_deal_value": best_alt, "dominance_margin": margin, "decision": "DEAL_DOMINATES" if margin > 0 else "NO_DEAL_OR_ALTERNATIVE_DOMINATES"}


class OutcomeCalibrationScore:
    def brier_score(self, predictions: Iterable[float], outcomes: Iterable[int]) -> float:
        p, o = list(predictions), list(outcomes)
        if len(p) != len(o) or not p:
            raise ValueError("predictions and outcomes must have equal non-zero length")
        if any(not 0 <= x <= 1 for x in p) or any(x not in (0, 1) for x in o):
            raise ValueError("invalid prediction or outcome")
        return sum((pi - oi) ** 2 for pi, oi in zip(p, o)) / len(p)
