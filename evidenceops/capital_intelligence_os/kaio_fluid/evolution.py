from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateImprovement:
    id: str
    accuracy_delta: float
    calibration_delta: float
    efficiency_delta: float
    complexity_delta: float
    safety_regression: bool = False
    authority_expansion: bool = False
    rollback_available: bool = True


@dataclass(frozen=True)
class EvolutionDecision:
    candidate_id: str
    score: float
    promote: bool
    reasons: tuple[str, ...]


class EvolutionGovernor:
    """Allow bounded cognitive improvement without self-granted authority or safety regression."""

    def evaluate(self, candidate: CandidateImprovement) -> EvolutionDecision:
        reasons: list[str] = []
        if candidate.safety_regression:
            reasons.append("SAFETY_REGRESSION")
        if candidate.authority_expansion:
            reasons.append("AUTHORITY_EXPANSION_FORBIDDEN")
        if not candidate.rollback_available:
            reasons.append("ROLLBACK_MISSING")

        score = (
            candidate.accuracy_delta * 0.40
            + candidate.calibration_delta * 0.25
            + candidate.efficiency_delta * 0.20
            - max(0.0, candidate.complexity_delta) * 0.15
            + max(0.0, -candidate.complexity_delta) * 0.10
        )
        if score <= 0:
            reasons.append("NO_NET_IMPROVEMENT")

        promote = not reasons and score > 0
        return EvolutionDecision(candidate.id, round(score, 6), promote, tuple(reasons))
