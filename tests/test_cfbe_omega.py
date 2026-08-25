import unittest

from benchmarking.cfbe_omega.baseline import BASELINE_DIMENSIONS
from benchmarking.cfbe_omega.benchmark_engine import (
    GapInput,
    best_of_breed_frontier,
    freshness_factor,
    gap_priority,
    leadership_state,
    weighted_score,
)


class CFBEOmegaTests(unittest.TestCase):
    def test_baseline_is_reproducible(self):
        score = weighted_score(BASELINE_DIMENSIONS)
        self.assertEqual(score.dimension_count, 20)
        self.assertEqual(score.total_weight, 120)
        self.assertEqual(score.raw_architecture, 56.0)
        self.assertEqual(round(score.proof_adjusted, 1), 40.4)

    def test_leadership_claim_fails_closed_without_provider_proof(self):
        self.assertEqual(
            leadership_state(
                90,
                80,
                provider_live=False,
                independently_replicated=False,
                no_critical_regression=True,
            ),
            "CANDIDATE_ADVANTAGE",
        )

    def test_frontier_is_best_of_breed_not_vendor_average(self):
        self.assertEqual(best_of_breed_frontier([71, 86, 64]), 86)

    def test_freshness_decay_has_floor(self):
        self.assertEqual(freshness_factor(30, 30), 1.0)
        self.assertEqual(freshness_factor(120, 30), 0.25)
        self.assertEqual(freshness_factor(1000, 30), 0.25)

    def test_gap_priority_is_bounded(self):
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
        self.assertEqual(score, 100.0)


if __name__ == "__main__":
    unittest.main()
