from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence


EVIDENCE_FACTORS = {
    "PROVIDER_LIVE_INDEPENDENT_READBACK": 1.00,
    "OPERATIONAL_SCOPED_REPEATED": 0.85,
    "DETERMINISTIC_CI_BOUNDED_RUNTIME": 0.70,
    "CONTROL_PLANE_OR_SOURCE_ONLY": 0.50,
    "PLANNED_OR_CLAIMED": 0.30,
}


@dataclass(frozen=True)
class Dimension:
    dimension_id: str
    name: str
    weight: float
    raw_score: float
    evidence_factor: float
    freshness_factor: float = 1.0

    def validate(self) -> None:
        if not self.dimension_id:
            raise ValueError("dimension_id is required")
        if self.weight <= 0:
            raise ValueError("weight must be > 0")
        if not 0 <= self.raw_score <= 5:
            raise ValueError("raw_score must be in [0, 5]")
        if not 0 <= self.evidence_factor <= 1:
            raise ValueError("evidence_factor must be in [0, 1]")
        if not 0 <= self.freshness_factor <= 1:
            raise ValueError("freshness_factor must be in [0, 1]")

    @property
    def raw_percent(self) -> float:
        self.validate()
        return (self.raw_score / 5.0) * 100.0

    @property
    def effective_percent(self) -> float:
        return self.raw_percent * self.evidence_factor * self.freshness_factor


@dataclass(frozen=True)
class AggregateScore:
    raw_architecture: float
    proof_adjusted: float
    total_weight: float
    dimension_count: int


@dataclass(frozen=True)
class GapInput:
    gap: float
    strategic_weight: float
    dependency_unlock: float
    risk_criticality: float
    feasibility: float
    cost: float
    irreversibility: float


def weighted_score(dimensions: Iterable[Dimension]) -> AggregateScore:
    dims = list(dimensions)
    if not dims:
        raise ValueError("at least one dimension is required")
    for dim in dims:
        dim.validate()
    total_weight = sum(dim.weight for dim in dims)
    raw = sum(dim.weight * dim.raw_percent for dim in dims) / total_weight
    proof = sum(dim.weight * dim.effective_percent for dim in dims) / total_weight
    return AggregateScore(
        raw_architecture=round(raw, 4),
        proof_adjusted=round(proof, 4),
        total_weight=total_weight,
        dimension_count=len(dims),
    )


def freshness_factor(age_days: float, ttl_days: float) -> float:
    """Conservative freshness decay.

    Fresh proof receives 1.0. After TTL, confidence decays linearly to a
    0.25 floor by 4x TTL. A stale source is not treated as absent; it is
    explicitly discounted until refreshed.
    """
    if age_days < 0 or ttl_days <= 0:
        raise ValueError("age_days must be >= 0 and ttl_days must be > 0")
    if age_days <= ttl_days:
        return 1.0
    ratio = age_days / ttl_days
    return max(0.25, round(1.0 - 0.25 * (ratio - 1.0), 4))


def gap_priority(value: GapInput) -> float:
    """Return normalized 0..100 gap priority.

    Inputs are normalized 0..1 except cost/irreversibility, which are also
    0..1 penalties. Unknown cost must be handled by the caller as fail-closed.
    """
    vals = (
        value.gap,
        value.strategic_weight,
        value.dependency_unlock,
        value.risk_criticality,
        value.feasibility,
        value.cost,
        value.irreversibility,
    )
    if any(not 0 <= x <= 1 for x in vals):
        raise ValueError("all gap inputs must be in [0, 1]")
    numerator = (
        value.gap
        * value.strategic_weight
        * value.dependency_unlock
        * value.risk_criticality
        * value.feasibility
    )
    denominator = 1.0 + value.cost + value.irreversibility
    return round(min(100.0, 100.0 * numerator / denominator), 4)


def leadership_state(
    internal_effective: float,
    frontier_threshold: float,
    *,
    provider_live: bool,
    independently_replicated: bool,
    no_critical_regression: bool,
    externally_distinguishable_advantage: bool = False,
) -> str:
    """Fail-closed benchmark claim classifier."""
    if internal_effective < frontier_threshold:
        return "GAP"
    if not provider_live:
        return "CANDIDATE_ADVANTAGE"
    if not independently_replicated or not no_critical_regression:
        return "FRONTIER_PARITY_UNPROVEN"
    if externally_distinguishable_advantage:
        return "FRONTIER_LEADER"
    return "FRONTIER_PARITY"


def best_of_breed_frontier(scores: Sequence[float]) -> float:
    if not scores:
        raise ValueError("at least one frontier score is required")
    if any(not 0 <= score <= 100 for score in scores):
        raise ValueError("frontier scores must be in [0, 100]")
    return max(scores)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

