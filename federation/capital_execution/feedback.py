from __future__ import annotations

from dataclasses import dataclass

from .models import stable_sha256


@dataclass(frozen=True)
class BacktestExecutionAssumption:
    commission_bps: float
    slippage_bps: float = 0.0

    def validate(self) -> None:
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("backtest execution assumptions cannot be negative")

    @property
    def total_cost_bps(self) -> float:
        self.validate()
        return float(self.commission_bps) + float(self.slippage_bps)


@dataclass(frozen=True)
class RealityCostObservation:
    spread_bps: float
    shadow_slippage_bps: float
    venue_fee_bps: float

    def validate(self) -> None:
        for name in ("spread_bps", "shadow_slippage_bps", "venue_fee_bps"):
            if float(getattr(self, name)) < 0:
                raise ValueError(f"{name} cannot be negative")

    @property
    def total_cost_bps(self) -> float:
        self.validate()
        return float(self.venue_fee_bps) + float(self.spread_bps) / 2.0 + float(self.shadow_slippage_bps)


@dataclass(frozen=True)
class ExecutionRealityDelta:
    assumed_total_cost_bps: float
    observed_total_cost_bps: float
    error_bps: float
    status: str
    tolerance_bps: float
    digest: str
    external_effect: bool = False
    financial_effect: bool = False


class BacktestRealityComparator:
    """Measures implementation-cost model error without changing a strategy or venue."""

    def compare(self, assumption: BacktestExecutionAssumption, observed: RealityCostObservation, *, tolerance_bps: float = 5.0) -> ExecutionRealityDelta:
        assumption.validate()
        observed.validate()
        if tolerance_bps < 0:
            raise ValueError("tolerance_bps cannot be negative")
        assumed = assumption.total_cost_bps
        actual = observed.total_cost_bps
        error = actual - assumed
        if error > tolerance_bps:
            status = "MODEL_UNDERESTIMATES_COSTS"
        elif error < -tolerance_bps:
            status = "MODEL_OVERESTIMATES_COSTS"
        else:
            status = "WITHIN_TOLERANCE"
        payload = {
            "assumed_total_cost_bps": assumed,
            "observed_total_cost_bps": actual,
            "error_bps": error,
            "status": status,
            "tolerance_bps": float(tolerance_bps),
            "external_effect": False,
            "financial_effect": False,
        }
        return ExecutionRealityDelta(assumed, actual, error, status, float(tolerance_bps), stable_sha256(payload))
