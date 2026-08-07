from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .models import Claim, EvidenceStatus, Alert
from .proofgraph import ProofGraph


class EpistemicShockIndex:
    """Quantifies how much a new claim destabilises a prior evidence state."""
    def score(self, graph: ProofGraph, new_claim: Claim) -> float:
        priors = graph.current_claims(new_claim.subject_id, new_claim.predicate)
        if not priors:
            return 0.0
        disagreement = sum(1 for p in priors if p.normalized_value() != new_claim.normalized_value()) / len(priors)
        prior_conf = sum(p.confidence for p in priors) / len(priors)
        status_weight = {
            EvidenceStatus.VERIFIED: 1.0, EvidenceStatus.CORROBORATED: 0.9,
            EvidenceStatus.USER_SUPPLIED: 0.6, EvidenceStatus.INFERENCE: 0.5,
            EvidenceStatus.MODEL_ESTIMATE: 0.45, EvidenceStatus.UNVERIFIED: 0.15,
        }[new_claim.status]
        return max(0.0, min(1.0, disagreement * prior_conf * status_weight))


class TrustDecayClock:
    def adjusted_confidence(self, confidence: float, age_days: float, freshness_sla_days: float, half_life_multiplier: float = 2.0) -> float:
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if age_days < 0 or freshness_sla_days <= 0 or half_life_multiplier <= 0:
            raise ValueError("invalid time parameters")
        if age_days <= freshness_sla_days:
            return confidence
        excess = age_days - freshness_sla_days
        half_life = freshness_sla_days * half_life_multiplier
        return max(0.0, min(confidence, confidence * (0.5 ** (excess / half_life))))


class AttentionCompressionEngine:
    def priority(self, *, materiality: float, uncertainty: float, irreversibility: float, deadline_pressure: float, auto_resolvability: float) -> float:
        values = [materiality, uncertainty, irreversibility, deadline_pressure, auto_resolvability]
        if any(not 0 <= x <= 1 for x in values):
            raise ValueError("all inputs must be between 0 and 1")
        raw = materiality * 0.34 + uncertainty * 0.20 + irreversibility * 0.24 + deadline_pressure * 0.22
        return max(0.0, min(1.0, raw * (1.0 - 0.65 * auto_resolvability)))

    def make_alert(self, subject_id: str, message: str, *, materiality: float, uncertainty: float, irreversibility: float, deadline_pressure: float, auto_resolvability: float) -> Alert | None:
        p = self.priority(materiality=materiality, uncertainty=uncertainty, irreversibility=irreversibility, deadline_pressure=deadline_pressure, auto_resolvability=auto_resolvability)
        if p < 0.28:
            return None
        return Alert(
            category="CRITICAL" if p >= 0.82 else "DECIDE" if p >= 0.65 else "REVIEW" if p >= 0.45 else "FYI",
            priority=p, message=message, subject_id=subject_id, requires_human=p >= 0.45,
            reason_codes=["ATTENTION_COMPRESSION"],
        )


class DecisionReversalThreshold:
    """Finds the nearest scalar assumption value that flips a signed decision margin."""
    def find(self, evaluator, baseline: float, lower: float, upper: float, tolerance: float = 1e-6, max_iter: int = 100) -> float | None:
        if not lower <= baseline <= upper:
            raise ValueError("baseline must be within bounds")
        baseline_margin = evaluator(baseline)
        if baseline_margin == 0:
            return baseline
        candidates: list[tuple[float, float]] = []
        for bound in (lower, upper):
            margin = evaluator(bound)
            if margin == 0 or margin * baseline_margin < 0:
                candidates.append((abs(bound - baseline), bound))
        if not candidates:
            return None
        _, bound = min(candidates)
        lo, hi = sorted((baseline, bound))
        for _ in range(max_iter):
            mid = (lo + hi) / 2
            margin = evaluator(mid)
            if abs(hi - lo) <= tolerance or margin == 0:
                return mid
            lo_margin = evaluator(lo)
            if lo_margin == 0:
                return lo
            if lo_margin * margin <= 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2


@dataclass(frozen=True)
class CounterfactualRegretResult:
    selected_value: float
    best_alternative_value: float
    regret: float
    normalized_regret: float


class CounterfactualCapitalRegret:
    def evaluate(self, selected_value: float, alternative_values: Iterable[float]) -> CounterfactualRegretResult:
        alternatives = list(alternative_values)
        best = max(alternatives) if alternatives else selected_value
        regret = max(0.0, best - selected_value)
        denom = max(abs(best), abs(selected_value), 1.0)
        return CounterfactualRegretResult(selected_value, best, regret, min(1.0, regret / denom))


class FragilityCascade:
    def propagate(self, graph: ProofGraph, origin: str, shock: float, attenuation: float = 0.72, max_depth: int = 6) -> Mapping[str, float]:
        if not 0 <= shock <= 1 or not 0 < attenuation <= 1:
            raise ValueError("invalid shock or attenuation")
        result: dict[str, float] = {origin: shock}
        frontier = [(origin, shock, 0)]
        while frontier:
            node, score, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            for child in sorted(graph.dependencies.get(node, ())):
                child_score = score * attenuation
                if child_score <= result.get(child, -1):
                    continue
                result[child] = child_score
                frontier.append((child, child_score, depth + 1))
        return result
