from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Hypothesis:
    hypothesis_id: str
    statement: str
    supporting_observations: list[str] = field(default_factory=list)
    conflicting_observations: list[str] = field(default_factory=list)
    predicted_evidence: list[str] = field(default_factory=list)
    falsifiers: list[str] = field(default_factory=list)
    confidence: float = 0.0


class OmegaScientia:
    def challenge(self, hypothesis: Hypothesis) -> dict[str, object]:
        return {
            "hypothesis": hypothesis.statement,
            "support": list(hypothesis.supporting_observations),
            "contradictions": list(hypothesis.conflicting_observations),
            "predicted_evidence": list(hypothesis.predicted_evidence),
            "falsifiers": list(hypothesis.falsifiers),
            "questions": [
                "What observation directly supports this?",
                "What competing explanation also fits?",
                "What evidence would falsify the preferred theory?",
                "Which next acquisition has the highest information gain?",
                "What result requires downgrade or retraction?",
            ],
        }


@dataclass(frozen=True)
class Route:
    route_id: str
    route_type: str
    feasibility: float
    proof_strength: float
    reversibility: float
    speed: float
    strategic_value: float
    owner_burden: float
    privacy_cost: float
    maintenance_cost: float


class FormationEngine:
    """Objective-preserving route generator/ranker primitive."""

    ROUTE_ORDER = (
        "REUSE",
        "EXTEND",
        "SPECIALISE",
        "COMPOSE",
        "ADAPT",
        "REROUTE",
        "ENGINEER",
        "NEW_BUILD",
    )

    @staticmethod
    def score(route: Route) -> float:
        return (
            route.feasibility
            + route.proof_strength
            + route.reversibility
            + route.speed
            + route.strategic_value
            - route.owner_burden
            - route.privacy_cost
            - route.maintenance_cost
        )

    def rank(self, routes: list[Route]) -> list[Route]:
        return sorted(routes, key=self.score, reverse=True)


@dataclass(frozen=True)
class Scenario:
    name: str
    consequence: float
    regret: float
    notes: str = ""


class FederationDigitalTwin:
    """Counterfactual simulator. Outputs are hypotheses, never facts."""

    def simulate(self, action: str, scenarios: list[Scenario]) -> dict[str, object]:
        return {
            "action": action,
            "scenarios": [
                {
                    "name": scenario.name,
                    "consequence": scenario.consequence,
                    "regret": scenario.regret,
                    "notes": scenario.notes,
                }
                for scenario in scenarios
            ],
            "maximum_regret": max((s.regret for s in scenarios), default=0.0),
            "truth_class": "SIMULATION_HYPOTHESIS",
        }
