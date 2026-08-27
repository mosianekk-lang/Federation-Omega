"""Robustness scoring for the Federation LONA Quant Node v2.

Research-only. This module scores evidence quality; it never authorizes broker execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable, Mapping


@dataclass(frozen=True)
class RunMetrics:
    total_return: float
    sharpe: float
    max_drawdown: float
    trades: int


@dataclass(frozen=True)
class RobustnessEvidence:
    holdout: RunMetrics
    benchmark: RunMetrics
    perturbations: tuple[RunMetrics, ...]
    cross_assets: tuple[RunMetrics, ...]
    adverse_cost: RunMetrics | None = None


def _positive_fraction(runs: Iterable[RunMetrics]) -> float:
    values = tuple(runs)
    if not values:
        return 0.0
    return sum(r.total_return > 0 for r in values) / len(values)


def _mean_sharpe(runs: Iterable[RunMetrics]) -> float:
    values = tuple(runs)
    if not values:
        return 0.0
    return mean(r.sharpe for r in values)


def promotion_score(e: RobustnessEvidence) -> Mapping[str, float | str]:
    """Return a conservative evidence score and state.

    The score rewards holdout risk-adjusted performance, benchmark competitiveness,
    perturbation stability, cross-asset survival and cost resilience. It intentionally
    penalizes high drawdown and tiny trade samples. Passing does not mean live-capital
    approval; it only advances research evidence.
    """
    benchmark_delta = e.holdout.total_return - e.benchmark.total_return
    perturbation_survival = _positive_fraction(e.perturbations)
    cross_asset_survival = _positive_fraction(e.cross_assets)
    perturbation_sharpe = _mean_sharpe(e.perturbations)
    cross_asset_sharpe = _mean_sharpe(e.cross_assets)

    score = 0.0
    score += min(max(e.holdout.sharpe, -1.0), 2.0) * 20.0
    score += max(min(benchmark_delta, 25.0), -25.0) * 0.6
    score += perturbation_survival * 15.0
    score += cross_asset_survival * 15.0
    score += min(max(perturbation_sharpe, -1.0), 2.0) * 7.5
    score += min(max(cross_asset_sharpe, -1.0), 2.0) * 7.5
    score -= max(e.holdout.max_drawdown - 20.0, 0.0) * 0.8
    if e.holdout.trades < 8:
        score -= 10.0
    if e.adverse_cost is not None:
        score += 10.0 if e.adverse_cost.total_return > 0 else -15.0

    if score >= 60 and e.holdout.sharpe >= 0.75 and perturbation_survival >= 0.67 and cross_asset_survival >= 0.5:
        state = "ROBUSTNESS_RESEARCH_ADMITTED"
    elif score >= 35:
        state = "REVISE_AND_RETEST"
    else:
        state = "REJECT_OR_QUARANTINE"

    return {
        "score": round(score, 2),
        "state": state,
        "benchmark_delta_return": round(benchmark_delta, 2),
        "perturbation_survival": round(perturbation_survival, 3),
        "cross_asset_survival": round(cross_asset_survival, 3),
    }
