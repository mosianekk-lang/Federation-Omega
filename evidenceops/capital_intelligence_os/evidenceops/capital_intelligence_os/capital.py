from __future__ import annotations

from typing import Iterable
from .models import CapitalCandidate, RankedCandidate


class GravityEngine:
    """Transparent deterministic cross-option capital-ranking engine."""
    def score(self, candidate: CapitalCandidate) -> float:
        candidate.validate()
        upside = candidate.expected_value * (0.25 + 0.75 * candidate.confidence) * (0.40 + 0.60 * candidate.strategic_fit) * (0.60 + 0.40 * candidate.optionality)
        burden = 1.0 + (0.30 * candidate.risk + 0.20 * candidate.capital_intensity + 0.15 * candidate.time_burden + 0.15 * candidate.complexity + 0.20 * candidate.opportunity_cost)
        return upside / burden

    def rank(self, candidates: Iterable[CapitalCandidate]) -> list[RankedCandidate]:
        scored = [(c, self.score(c)) for c in list(candidates)]
        scored.sort(key=lambda item: (-item[1], item[0].candidate_id))
        return [RankedCandidate(c.candidate_id, score, c.expected_value, idx + 1, c.metadata) for idx, (c, score) in enumerate(scored)]


class FinancingStressEngine:
    def annual_interest_delta(self, debt_principal: float, basis_points_change: float) -> float:
        if debt_principal < 0:
            raise ValueError("debt_principal must be non-negative")
        return debt_principal * (basis_points_change / 10_000.0)

    def irr_proxy_delta(self, equity_value: float, annual_cashflow_delta: float, hold_years: int) -> float:
        if equity_value <= 0 or hold_years <= 0:
            raise ValueError("equity_value and hold_years must be positive")
        return annual_cashflow_delta * hold_years / equity_value
