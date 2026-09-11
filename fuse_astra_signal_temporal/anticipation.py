from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import sqrt
from statistics import fmean
from typing import Sequence


class TrendDirection(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"


class Regime(str, Enum):
    BASELINE = "baseline"
    SHIFTING = "shifting"
    ELEVATED = "elevated"
    DEPRESSED = "depressed"
    VOLATILE = "volatile"


class TemporalAction(str, Enum):
    WAIT = "wait"
    WATCH = "watch"
    INVESTIGATE = "investigate"
    PREPARE = "prepare"
    ACT = "act"
    HOLD = "hold"


class OpportunityPhase(str, Enum):
    TOO_EARLY = "too_early"
    EMERGING = "emerging"
    ACTIONABLE = "actionable"
    CROWDED = "crowded"
    DECLINING = "declining"
    EXPIRED = "expired"


@dataclass(frozen=True)
class TimeValue:
    time_ms: int
    value: float


@dataclass(frozen=True)
class TrendEstimate:
    direction: TrendDirection
    slope_per_ms: float
    intercept: float
    r2: float
    residual_std: float


class TrendEstimator:
    @staticmethod
    def fit(points: Sequence[TimeValue], *, flat_epsilon: float = 1e-9) -> TrendEstimate:
        if len(points) < 2:
            raise ValueError("at least two points are required")
        ordered = sorted(points, key=lambda p: p.time_ms)
        x0 = ordered[0].time_ms
        xs = [float(p.time_ms - x0) for p in ordered]
        ys = [float(p.value) for p in ordered]
        x_mean = fmean(xs)
        y_mean = fmean(ys)
        sxx = sum((x - x_mean) ** 2 for x in xs)
        if sxx == 0:
            raise ValueError("time points must not all be identical")
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sxx
        intercept_local = y_mean - slope * x_mean
        predicted = [intercept_local + slope * x for x in xs]
        ss_res = sum((y - yhat) ** 2 for y, yhat in zip(ys, predicted))
        ss_tot = sum((y - y_mean) ** 2 for y in ys)
        r2 = 1.0 if ss_tot == 0 and ss_res == 0 else (0.0 if ss_tot == 0 else max(0.0, 1.0 - ss_res / ss_tot))
        residual_std = sqrt(ss_res / len(ys))
        if slope > flat_epsilon:
            direction = TrendDirection.RISING
        elif slope < -flat_epsilon:
            direction = TrendDirection.FALLING
        else:
            direction = TrendDirection.FLAT
        intercept = intercept_local - slope * x0
        return TrendEstimate(direction, slope, intercept, r2, residual_std)


@dataclass(frozen=True)
class ForecastPoint:
    target_time_ms: int
    estimate: float
    lower: float
    upper: float
    confidence: float


class ForecastEngine:
    @staticmethod
    def linear(
        points: Sequence[TimeValue],
        *,
        target_time_ms: int,
        uncertainty_multiplier: float = 2.0,
    ) -> ForecastPoint:
        trend = TrendEstimator.fit(points)
        estimate = trend.intercept + trend.slope_per_ms * target_time_ms
        last_time = max(p.time_ms for p in points)
        span = max(1, last_time - min(p.time_ms for p in points))
        horizon_ratio = max(0.0, target_time_ms - last_time) / span
        uncertainty = uncertainty_multiplier * trend.residual_std * sqrt(1.0 + horizon_ratio)
        confidence = max(0.0, min(1.0, trend.r2 / (1.0 + horizon_ratio)))
        return ForecastPoint(target_time_ms, estimate, estimate - uncertainty, estimate + uncertainty, confidence)


@dataclass(frozen=True)
class LeadLagEstimate:
    lag_steps: int
    correlation: float
    samples: int


class LeadLagAnalyzer:
    @staticmethod
    def _corr(a: Sequence[float], b: Sequence[float]) -> float:
        if len(a) != len(b) or len(a) < 2:
            return 0.0
        ma = fmean(a)
        mb = fmean(b)
        da = [x - ma for x in a]
        db = [x - mb for x in b]
        denom = sqrt(sum(x * x for x in da) * sum(y * y for y in db))
        if denom == 0:
            return 0.0
        return sum(x * y for x, y in zip(da, db)) / denom

    @classmethod
    def best_lag(cls, leading: Sequence[float], target: Sequence[float], *, max_lag_steps: int, min_samples: int = 3) -> LeadLagEstimate:
        if len(leading) != len(target):
            raise ValueError("series must have equal length")
        if max_lag_steps < 0:
            raise ValueError("max_lag_steps must be nonnegative")
        best = LeadLagEstimate(0, 0.0, 0)
        found = False
        for lag in range(-max_lag_steps, max_lag_steps + 1):
            if lag >= 0:
                a = leading[: len(leading) - lag or None]
                b = target[lag:]
            else:
                shift = -lag
                a = leading[shift:]
                b = target[: len(target) - shift]
            if len(a) < min_samples:
                continue
            corr = cls._corr(a, b)
            cand = LeadLagEstimate(lag, corr, len(a))
            if not found or abs(corr) > abs(best.correlation) or (abs(corr) == abs(best.correlation) and abs(lag) < abs(best.lag_steps)):
                best = cand
                found = True
        if not found:
            raise ValueError("insufficient samples for requested lag search")
        return best


@dataclass(frozen=True)
class RegimeEstimate:
    regime: Regime
    z_mean: float
    volatility_ratio: float


class RegimeClassifier:
    @staticmethod
    def classify(baseline: Sequence[float], recent: Sequence[float], *, shift_z: float = 2.0, volatility_multiplier: float = 2.0) -> RegimeEstimate:
        if len(baseline) < 2 or len(recent) < 2:
            raise ValueError("baseline and recent require at least two points")
        bmean = fmean(baseline)
        rmean = fmean(recent)
        bvar = sum((x - bmean) ** 2 for x in baseline) / len(baseline)
        rvar = sum((x - rmean) ** 2 for x in recent) / len(recent)
        bstd = sqrt(bvar)
        rstd = sqrt(rvar)
        if bstd == 0:
            z = 0.0 if rmean == bmean else (float("inf") if rmean > bmean else float("-inf"))
            volatility_ratio = float("inf") if rstd > 0 else 1.0
        else:
            z = (rmean - bmean) / bstd
            volatility_ratio = rstd / bstd
        if volatility_ratio >= volatility_multiplier:
            regime = Regime.VOLATILE
        elif z >= shift_z:
            regime = Regime.ELEVATED
        elif z <= -shift_z:
            regime = Regime.DEPRESSED
        elif abs(z) >= shift_z / 2:
            regime = Regime.SHIFTING
        else:
            regime = Regime.BASELINE
        return RegimeEstimate(regime, z, volatility_ratio)


@dataclass(frozen=True)
class EarlyWarning:
    probability: float
    lead_time_ms: int | None
    confidence: float
    reason: str


class EarlyWarningEngine:
    @staticmethod
    def score(*, fused_confidence: float, salience: float, lead_lag_correlation: float, persistence: float, threshold_distance: float, estimated_rate_per_ms: float) -> EarlyWarning:
        vals = [fused_confidence, salience, abs(lead_lag_correlation), persistence]
        if any(not 0.0 <= v <= 1.0 for v in vals):
            raise ValueError("confidence/salience/correlation/persistence must map to [0,1]")
        probability = max(0.0, min(1.0, 0.30 * fused_confidence + 0.25 * salience + 0.25 * abs(lead_lag_correlation) + 0.20 * persistence))
        lead_time = None
        if threshold_distance > 0 and estimated_rate_per_ms > 0:
            lead_time = int(threshold_distance / estimated_rate_per_ms)
        confidence = max(0.0, min(1.0, fused_confidence * (0.5 + 0.5 * abs(lead_lag_correlation))))
        reason = "corroborated leading signal" if lead_time is not None else "risk signal without positive crossing-rate estimate"
        return EarlyWarning(probability, lead_time, confidence, reason)


class TemporalActionAdvisor:
    @staticmethod
    def advise(*, probability: float, confidence: float, lead_time_ms: int | None, failure_cost: float, reversibility: float, authority_ready: bool, evidence_fresh: bool) -> TemporalAction:
        for value in (probability, confidence, failure_cost, reversibility):
            if not 0.0 <= value <= 1.0:
                raise ValueError("probability/confidence/failure_cost/reversibility must be in [0,1]")
        if not evidence_fresh:
            return TemporalAction.INVESTIGATE
        if not authority_ready and probability >= 0.8 and failure_cost >= 0.7:
            return TemporalAction.HOLD
        urgency = probability * confidence * (0.5 + 0.5 * failure_cost)
        if lead_time_ms is not None and lead_time_ms > 60 * 60 * 1000 and urgency < 0.45:
            return TemporalAction.WATCH
        if urgency >= 0.75 and reversibility >= 0.5 and authority_ready:
            return TemporalAction.ACT
        if urgency >= 0.55:
            return TemporalAction.PREPARE if authority_ready else TemporalAction.HOLD
        if urgency >= 0.30:
            return TemporalAction.INVESTIGATE
        return TemporalAction.WAIT


class OpportunityClassifier:
    @staticmethod
    def classify(*, momentum: float, evidence: float, adoption: float, saturation: float, decay: float) -> OpportunityPhase:
        for value in (momentum, evidence, adoption, saturation, decay):
            if not 0.0 <= value <= 1.0:
                raise ValueError("opportunity features must be in [0,1]")
        if decay >= 0.8 and momentum <= 0.2:
            return OpportunityPhase.EXPIRED
        if decay >= 0.55 or momentum < 0.25:
            return OpportunityPhase.DECLINING
        if saturation >= 0.8 and adoption >= 0.7:
            return OpportunityPhase.CROWDED
        if evidence >= 0.65 and momentum >= 0.55 and saturation < 0.75:
            return OpportunityPhase.ACTIONABLE
        if momentum >= 0.35 and evidence >= 0.35:
            return OpportunityPhase.EMERGING
        return OpportunityPhase.TOO_EARLY
