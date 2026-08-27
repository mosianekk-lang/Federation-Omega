from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable, Mapping, Any

from .capital_intent import ADMITTED_RESEARCH_STATE, QuantResearchEvidence
from .models import stable_sha256


@dataclass(frozen=True)
class PortfolioCandidate:
    evidence: QuantResearchEvidence
    correlation_penalty: float = 0.0
    tail_risk: float = 0.0
    implementation_cost: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.evidence.validate()
        for name in ("correlation_penalty", "tail_risk", "implementation_cost"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class PortfolioAllocation:
    strategy_id: str
    instrument_id: str
    target_weight: float
    utility_score: float
    evidence_ref: str


@dataclass(frozen=True)
class PortfolioDecision:
    portfolio_id: str
    allocations: tuple[PortfolioAllocation, ...]
    cash_weight: float
    rejected: Mapping[str, tuple[str, ...]]
    decision_digest: str
    executable: bool = False
    financial_effect: bool = False


class PortfolioIntelligenceEngine:
    """Evidence-weighted portfolio allocator. It emits portfolio weights, never venue orders."""

    def utility(self, candidate: PortfolioCandidate) -> float:
        candidate.validate()
        e = candidate.evidence
        if e.research_state != ADMITTED_RESEARCH_STATE:
            return 0.0
        if e.excess_return_pct <= 0:
            return 0.0
        confidence = max(0.0, min(1.0, e.robustness_score * (1.0 - e.uncertainty)))
        reward = e.excess_return_pct * confidence * (0.40 + 0.60 * e.regime_fit) * (0.40 + 0.60 * e.liquidity_quality)
        drawdown_penalty = min(1.0, e.maximum_drawdown_pct / 50.0)
        risk_load = (
            0.35 * drawdown_penalty
            + 0.25 * candidate.correlation_penalty
            + 0.20 * candidate.tail_risk
            + 0.20 * candidate.implementation_cost
        )
        return max(0.0, reward / (1.0 + risk_load))

    def allocate(
        self,
        *,
        portfolio_id: str,
        candidates: Iterable[PortfolioCandidate],
        maximum_invested_weight: float = 0.25,
        maximum_single_weight: float = 0.08,
        minimum_trades: int = 8,
        minimum_robustness: float = 0.60,
        maximum_drawdown_pct: float = 30.0,
    ) -> PortfolioDecision:
        if not 0.0 <= maximum_invested_weight <= 1.0:
            raise ValueError("maximum_invested_weight must be between 0 and 1")
        if not 0.0 <= maximum_single_weight <= 1.0:
            raise ValueError("maximum_single_weight must be between 0 and 1")
        if maximum_single_weight > maximum_invested_weight:
            raise ValueError("maximum_single_weight cannot exceed maximum_invested_weight")

        accepted: list[tuple[PortfolioCandidate, float]] = []
        rejected: dict[str, tuple[str, ...]] = {}
        for candidate in list(candidates):
            candidate.validate()
            e = candidate.evidence
            reasons: list[str] = []
            if e.research_state != ADMITTED_RESEARCH_STATE:
                reasons.append("RESEARCH_NOT_ADMITTED")
            if e.excess_return_pct <= 0:
                reasons.append("NO_POSITIVE_EXCESS_RETURN")
            if e.sample_trades < minimum_trades:
                reasons.append("SAMPLE_TOO_SMALL")
            if e.robustness_score < minimum_robustness:
                reasons.append("ROBUSTNESS_BELOW_FLOOR")
            if e.maximum_drawdown_pct > maximum_drawdown_pct:
                reasons.append("DRAWDOWN_ABOVE_LIMIT")
            score = self.utility(candidate)
            if score <= 0 and not reasons:
                reasons.append("NON_POSITIVE_UTILITY")
            if reasons:
                rejected[e.strategy_id] = tuple(sorted(set(reasons)))
            else:
                accepted.append((candidate, score))

        accepted.sort(key=lambda item: (-item[1], item[0].evidence.strategy_id))
        score_sum = sum(score for _, score in accepted)
        allocations: list[PortfolioAllocation] = []
        remaining = maximum_invested_weight
        if score_sum > 0:
            for candidate, score in accepted:
                if remaining <= 0:
                    break
                raw = maximum_invested_weight * (score / score_sum)
                weight = min(maximum_single_weight, raw, remaining)
                if weight <= 0:
                    continue
                e = candidate.evidence
                allocations.append(PortfolioAllocation(e.strategy_id, e.instrument_id, weight, score, e.evidence_ref))
                remaining -= weight

        invested = sum(a.target_weight for a in allocations)
        cash_weight = max(0.0, 1.0 - invested)
        digest_payload = {
            "portfolio_id": portfolio_id,
            "allocations": [asdict(a) for a in allocations],
            "cash_weight": cash_weight,
            "rejected": {k: list(v) for k, v in sorted(rejected.items())},
            "executable": False,
            "financial_effect": False,
        }
        return PortfolioDecision(
            portfolio_id=portfolio_id,
            allocations=tuple(allocations),
            cash_weight=cash_weight,
            rejected=rejected,
            decision_digest=stable_sha256(digest_payload),
        )
