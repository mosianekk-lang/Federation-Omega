from __future__ import annotations

from typing import Iterable
import math


class SignalDivergenceIndex:
    def score(self, fundamental: float, market: float, confidence: float = 1.0) -> float:
        if any(not 0 <= x <= 1 for x in (fundamental, market, confidence)):
            raise ValueError("inputs must be between 0 and 1")
        return abs(fundamental - market) * confidence


class DealFragilitySurface:
    """Combine normalized 0..1 fragility dimensions.

    Financial leverage is commonly supplied as a ratio (for example 1.6x), not
    as a normalized stress score. `leverage_stress_from_ratio` performs that
    explicit conversion before this surface is called. The default 5.0x anchor
    is a transparent reference-model parameter, not an empirical distress claim.
    """

    @staticmethod
    def leverage_stress_from_ratio(leverage_ratio: float, *, stress_at_ratio: float = 5.0) -> float:
        if not math.isfinite(leverage_ratio) or leverage_ratio < 0:
            raise ValueError("leverage ratio must be finite and non-negative")
        if not math.isfinite(stress_at_ratio) or stress_at_ratio <= 0:
            raise ValueError("leverage stress reference must be finite and positive")
        return min(1.0, leverage_ratio / stress_at_ratio)

    def score(
        self,
        *,
        financing_stress: float,
        regulatory_uncertainty: float,
        market_volatility: float,
        synergy_dependence: float,
        leverage: float,
    ) -> float:
        xs = (financing_stress, regulatory_uncertainty, market_volatility, synergy_dependence, leverage)
        if any(not 0 <= x <= 1 for x in xs):
            raise ValueError("fragility dimensions must be between 0 and 1")
        base = (
            0.24 * financing_stress
            + 0.22 * regulatory_uncertainty
            + 0.16 * market_volatility
            + 0.20 * synergy_dependence
            + 0.18 * leverage
        )
        interaction = 0.25 * max(financing_stress, leverage) * max(regulatory_uncertainty, synergy_dependence)
        return min(1.0, base + interaction)


class TransactionWindowRadar:
    def score(
        self,
        *,
        valuation_attractiveness: float,
        financing_availability: float,
        volatility_inverse: float,
        buyer_activity: float,
        strategic_urgency: float,
    ) -> float:
        xs = (
            valuation_attractiveness,
            financing_availability,
            volatility_inverse,
            buyer_activity,
            strategic_urgency,
        )
        if any(not 0 <= x <= 1 for x in xs):
            raise ValueError("window dimensions must be between 0 and 1")
        return (
            0.25 * valuation_attractiveness
            + 0.22 * financing_availability
            + 0.16 * volatility_inverse
            + 0.17 * buyer_activity
            + 0.20 * strategic_urgency
        )


class AnnouncementMoveDecomposer:
    """Computes abnormal return only; it does not infer transaction causation."""

    def abnormal_return(self, security_return: float, benchmark_return: float, beta: float = 1.0) -> float:
        if not all(math.isfinite(x) for x in (security_return, benchmark_return, beta)):
            raise ValueError("returns/beta must be finite")
        return security_return - beta * benchmark_return


class PortfolioConcentrationRadar:
    def herfindahl(self, exposures: Iterable[float]) -> float:
        values = [abs(float(x)) for x in exposures]
        total = sum(values)
        if total == 0:
            return 0.0
        return sum((x / total) ** 2 for x in values)


class SpreadPersistenceMonitor:
    def persistence(self, gaps: Iterable[float]) -> dict[str, float]:
        values = list(gaps)
        if not values:
            raise ValueError("gaps required")
        mean = sum(values) / len(values)
        last = values[-1]
        same_sign = sum(1 for x in values if (x >= 0) == (mean >= 0)) / len(values)
        return {
            "mean_gap": mean,
            "latest_gap": last,
            "sign_persistence": same_sign,
            "absolute_mean_gap": sum(abs(x) for x in values) / len(values),
        }


class LiquidityStressPenalty:
    def penalty(self, *, spread_pct: float, turnover_ratio: float, volatility: float) -> float:
        if spread_pct < 0 or turnover_ratio < 0 or volatility < 0:
            raise ValueError("liquidity inputs cannot be negative")
        return min(
            1.0,
            0.45 * min(1.0, spread_pct / 0.05)
            + 0.30 * (1.0 - min(1.0, turnover_ratio))
            + 0.25 * min(1.0, volatility / 0.8),
        )
