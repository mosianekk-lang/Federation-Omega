from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .market_algorithms import DealFragilitySurface, SignalDivergenceIndex, TransactionWindowRadar
from .market_intelligence import DealCompletionProbabilityEngine, FundamentalSignal, MarketDealTerms
from .models import utc_now_iso


@dataclass(frozen=True)
class DealMarketAssessment:
    fundamental_probability: float
    market_implied_proxy: float
    expectation_gap: float
    divergence_index: float
    fragility_score: float
    generated_at: str = field(default_factory=utc_now_iso)
    caveats: tuple[str, ...] = (
        "Market-implied probability is a simplified scenario-price proxy, not a fact or trading recommendation.",
        "Public-market reaction must not be treated as proof that a transaction creates or destroys value.",
        "Leverage is converted from a raw ratio into a bounded reference-model stress dimension before fragility scoring; the default 5.0x anchor is not an empirical distress threshold.",
    )


class MarketIntelligenceService:
    def __init__(self) -> None:
        self.probability = DealCompletionProbabilityEngine()
        self.divergence = SignalDivergenceIndex()
        self.fragility = DealFragilitySurface()
        self.window = TransactionWindowRadar()

    def assess_deal(
        self,
        signals: Iterable[FundamentalSignal],
        terms: MarketDealTerms,
        *,
        financing_stress: float,
        regulatory_uncertainty: float,
        market_volatility: float,
        synergy_dependence: float,
        leverage: float,
        evidence_confidence: float = 1.0,
        leverage_stress_reference: float = 5.0,
    ) -> DealMarketAssessment:
        fundamental = self.probability.fundamental(signals)
        market = self.probability.market_implied_proxy(terms)
        gap = self.probability.expectation_gap(fundamental, market)
        leverage_stress = self.fragility.leverage_stress_from_ratio(
            leverage,
            stress_at_ratio=leverage_stress_reference,
        )
        return DealMarketAssessment(
            fundamental,
            market,
            gap,
            self.divergence.score(fundamental, market, evidence_confidence),
            self.fragility.score(
                financing_stress=financing_stress,
                regulatory_uncertainty=regulatory_uncertainty,
                market_volatility=market_volatility,
                synergy_dependence=synergy_dependence,
                leverage=leverage_stress,
            ),
        )
