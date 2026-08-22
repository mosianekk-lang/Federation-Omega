from benchmarking.cfbe_omega.baseline import BASELINE_DIMENSIONS
from benchmarking.cfbe_omega.benchmark_engine import (
    GapInput,
    best_of_breed_frontier,
    freshness_factor,
    gap_priority,
    leadership_state,
    weighted_score,
)


def test_baseline_is_reproducible():
    score = weighted_score(BASELINE_DIMENSIONS)
    assert score.dimension_count == 20
    assert score.total_weight == 120
    assert score.raw_architecture == 56.0
    assert round(score.proof_adjusted, 1) == 40.4


def test_leadership_claim_fails_closed_without_provider_proof():
    assert leadership_state(
        90,
        80,
        provider_live=False,
        independently_replicated=False,
        no_critical_regression=True,
    ) == "CANDIDATE_ADVANTAGE"


def test_frontier_is_best_of_breed_not_vendor_average():
    assert best_of_breed_frontier([71, 86, 64]) == 86


def test_freshness_decay_has_floor():
    assert freshness_factor(30, 30) == 1.0
    assert freshness_factor(120, 30) == 0.25
    assert freshness_factor(1000, 30) == 0.25


def test_gap_priority_is_bounded():
    score = gap_priority(
        GapInput(
            gap=1.0,
            strategic_weight=1.0,
            dependency_unlock=1.0,
            risk_criticality=1.0,
            feasibility=1.0,
            cost=0.0,
            irreversibility=0.0,
        )
    )
    assert score == 100.0
