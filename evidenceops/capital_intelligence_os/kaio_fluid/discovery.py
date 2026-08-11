from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepresentationCandidate:
    name: str
    description: str
    score: float


class DiscoveryEngine:
    """Generate alternate representations and identify unexplained residuals."""

    REPRESENTATIONS = (
        ("TIMELINE", "Represent events and state transitions over time."),
        ("GRAPH", "Represent entities, dependencies and provenance relationships."),
        ("CAUSAL", "Represent mechanisms, confounders and outcomes."),
        ("CONSTRAINT", "Represent hard constraints, assumptions and degrees of freedom."),
        ("GAME_TREE", "Represent strategic actions, reactions and contingencies."),
        ("ELEMENT_MATRIX", "Represent required elements and supporting proof."),
    )

    def representation_tournament(
        self,
        *,
        temporal_density: float,
        dependency_density: float,
        causal_uncertainty: float,
        strategic_interaction: float,
        element_structure: float,
    ) -> tuple[RepresentationCandidate, ...]:
        scores = {
            "TIMELINE": temporal_density,
            "GRAPH": dependency_density,
            "CAUSAL": causal_uncertainty,
            "CONSTRAINT": max(dependency_density, causal_uncertainty) * 0.8,
            "GAME_TREE": strategic_interaction,
            "ELEMENT_MATRIX": element_structure,
        }
        ranked = [
            RepresentationCandidate(name, desc, max(0.0, min(1.0, scores[name])))
            for name, desc in self.REPRESENTATIONS
        ]
        return tuple(sorted(ranked, key=lambda item: (-item.score, item.name)))

    def residuals(self, observations: set[str], explained: set[str]) -> tuple[str, ...]:
        return tuple(sorted(observations - explained))

    def unknown_frontier(self, residuals: tuple[str, ...], surprises: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*residuals, *surprises)))

    def paradigm_escape_needed(
        self,
        *,
        exception_count: int,
        failed_predictions: int,
        unresolved_contradictions: int,
        reasoning_debt: int,
    ) -> bool:
        pressure = exception_count + 2 * failed_predictions + unresolved_contradictions + reasoning_debt
        return pressure >= 8
