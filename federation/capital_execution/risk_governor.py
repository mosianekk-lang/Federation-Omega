from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

from .models import stable_sha256


@dataclass(frozen=True)
class RiskLimits:
    maximum_position_weight: float = 0.08
    maximum_order_notional: float = 100000.0
    maximum_spread_bps: float = 80.0
    maximum_slippage_bps: float = 50.0
    minimum_depth_ratio: float = 1.5
    maximum_daily_loss_pct: float = 2.0
    maximum_drawdown_pct: float = 10.0
    maximum_market_age_seconds: float = 10.0

    def validate(self) -> None:
        if not 0 < self.maximum_position_weight <= 1:
            raise ValueError("maximum_position_weight must be in (0,1]")
        for name in (
            "maximum_order_notional",
            "maximum_spread_bps",
            "maximum_slippage_bps",
            "minimum_depth_ratio",
            "maximum_daily_loss_pct",
            "maximum_drawdown_pct",
            "maximum_market_age_seconds",
        ):
            if float(getattr(self, name)) < 0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True)
class RiskContext:
    desired_position_weight: float
    order_notional: float
    spread_bps: float
    simulated_slippage_bps: float
    depth_ratio: float
    daily_loss_pct: float
    drawdown_pct: float
    market_age_seconds: float
    venue_healthy: bool
    reconciliation_healthy: bool
    kill_switch_active: bool = False
    mode: str = "SHADOW"


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    mode: str
    reason_codes: tuple[str, ...]
    decision_digest: str
    external_effect: bool = False
    financial_effect: bool = False


class CapitalRiskGovernor:
    """Independent deterministic veto. Strategies and CIOS cannot override it."""

    def evaluate(self, context: RiskContext, limits: RiskLimits | None = None) -> RiskDecision:
        limits = limits or RiskLimits()
        limits.validate()
        reasons: list[str] = []

        if context.mode != "SHADOW":
            reasons.append("V1_SHADOW_MODE_ONLY")
        if context.kill_switch_active:
            reasons.append("KILL_SWITCH_ACTIVE")
        if not context.venue_healthy:
            reasons.append("VENUE_UNHEALTHY")
        if not context.reconciliation_healthy:
            reasons.append("RECONCILIATION_UNHEALTHY")
        if not 0 <= context.desired_position_weight <= limits.maximum_position_weight:
            reasons.append("POSITION_WEIGHT_LIMIT")
        if context.order_notional < 0 or context.order_notional > limits.maximum_order_notional:
            reasons.append("ORDER_NOTIONAL_LIMIT")
        if context.spread_bps < 0 or context.spread_bps > limits.maximum_spread_bps:
            reasons.append("SPREAD_LIMIT")
        if context.simulated_slippage_bps < 0 or context.simulated_slippage_bps > limits.maximum_slippage_bps:
            reasons.append("SLIPPAGE_LIMIT")
        if context.depth_ratio < limits.minimum_depth_ratio:
            reasons.append("DEPTH_LIMIT")
        if context.daily_loss_pct > limits.maximum_daily_loss_pct:
            reasons.append("DAILY_LOSS_LIMIT")
        if context.drawdown_pct > limits.maximum_drawdown_pct:
            reasons.append("DRAWDOWN_LIMIT")
        if context.market_age_seconds < 0 or context.market_age_seconds > limits.maximum_market_age_seconds:
            reasons.append("STALE_MARKET_DATA")

        payload: Mapping[str, Any] = {
            "context": asdict(context),
            "limits": asdict(limits),
            "allowed": not reasons,
            "reasons": tuple(reasons),
            "external_effect": False,
            "financial_effect": False,
        }
        return RiskDecision(
            allowed=not reasons,
            mode=context.mode,
            reason_codes=tuple(reasons),
            decision_digest=stable_sha256(payload),
        )
