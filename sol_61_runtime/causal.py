from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class CausalEdge:
    cause: str
    effect: str
    strength: float
    confidence: float
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Intervention:
    intervention_id: str
    target: str
    expected_effect: float
    cost: float
    risk: float
    reversibility: float


class CausalDecisionEngine:
    """Provider-neutral causal reasoning reference layer.

    It ranks interventions using explicit causal evidence and rejects repairs
    that address only a symptom when an upstream cause is known.
    """

    def __init__(self) -> None:
        self.edges: list[CausalEdge] = []
        self.hypotheses: dict[str, float] = {}
        self.interventions: dict[str, Intervention] = {}
        self.measurements: list[dict[str, Any]] = []

    def add_edge(self, edge: CausalEdge) -> None:
        if not 0 <= edge.confidence <= 1 or not -1 <= edge.strength <= 1:
            raise ValueError("invalid causal edge")
        self.edges.append(edge)

    def register_hypothesis(self, hypothesis_id: str, prior: float) -> None:
        if not 0 < prior < 1:
            raise ValueError("prior must be between zero and one")
        self.hypotheses[hypothesis_id] = prior

    def update_hypothesis(self, hypothesis_id: str, likelihood_if_true: float, likelihood_if_false: float) -> float:
        prior = self.hypotheses[hypothesis_id]
        numerator = likelihood_if_true * prior
        denominator = numerator + likelihood_if_false * (1 - prior)
        posterior = numerator / denominator if denominator else prior
        self.hypotheses[hypothesis_id] = posterior
        return posterior

    def add_intervention(self, intervention: Intervention) -> None:
        self.interventions[intervention.intervention_id] = intervention

    def upstream_causes(self, node: str, min_confidence: float = 0.5) -> set[str]:
        result, frontier = set(), [node]
        while frontier:
            current = frontier.pop()
            for edge in self.edges:
                if edge.effect == current and edge.confidence >= min_confidence and edge.cause not in result:
                    result.add(edge.cause)
                    frontier.append(edge.cause)
        return result

    def is_symptom_only(self, intervention_id: str, symptom: str) -> bool:
        target = self.interventions[intervention_id].target
        upstream = self.upstream_causes(symptom)
        return target == symptom and bool(upstream)

    def rank_interventions(self, symptom: str) -> list[dict[str, Any]]:
        upstream = self.upstream_causes(symptom)
        ranked = []
        for item in self.interventions.values():
            causal_fit = 1.0 if item.target in upstream else 0.35 if item.target == symptom else 0.1
            score = (
                item.expected_effect * causal_fit * item.reversibility
                - item.cost * 0.15
                - item.risk * 0.35
            )
            ranked.append({"intervention": asdict(item), "causal_fit": causal_fit, "score": round(score, 6), "symptom_only": item.target == symptom and bool(upstream)})
        return sorted(ranked, key=lambda row: (-row["score"], row["intervention"]["intervention_id"]))

    def counterfactual(self, intervention_id: str, baseline: float) -> dict[str, float]:
        item = self.interventions[intervention_id]
        predicted = baseline * (1 - max(0.0, min(1.0, item.expected_effect)))
        return {"baseline": baseline, "predicted_after": predicted, "delta": predicted - baseline}

    def measure_effect(self, intervention_id: str, before: float, after: float) -> dict[str, Any]:
        actual = 0.0 if before == 0 else (before - after) / abs(before)
        expected = self.interventions[intervention_id].expected_effect
        row = {
            "intervention_id": intervention_id,
            "before": before,
            "after": after,
            "actual_effect": actual,
            "expected_effect": expected,
            "error": actual - expected,
            "effective": actual > 0,
        }
        self.measurements.append(row)
        return row
