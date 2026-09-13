import unittest

from superior_logic.market_composite_benchmark import (
    BenchmarkIntegrityCourt,
    BenchmarkObservation,
    BenchmarkTask,
    MarketCompositeCourt,
)


def tasks(n=20):
    return tuple(
        BenchmarkTask(
            task_id=f"T{i:02d}",
            source_epoch=f"S{i:02d}",
            environment_profile="ENV1",
            oracle_id=f"O{i:02d}",
            hard_floors=("QUALITY", "SECURITY", "PROOF"),
        )
        for i in range(n)
    )


def observations(system_id, system_class, n=20, *, accepted=True, causal=.9, quality=.9, floor=True, owner=0, escapes=0, wall=100.0, cost=100.0):
    return tuple(
        BenchmarkObservation(
            task_id=f"T{i:02d}",
            system_id=system_id,
            system_class=system_class,
            accepted=accepted,
            causal_accuracy=causal,
            quality_score=quality,
            hard_floor_pass=floor,
            owner_interventions=owner,
            regression_escapes=escapes,
            wall_time_seconds=wall / n,
            cost_units=cost / n,
        )
        for i in range(n)
    )


class MarketCompositeBenchmarkTests(unittest.TestCase):
    def test_integrity_holds_non_frozen_task_out_of_scoring(self):
        cohort = tasks(2) + (
            BenchmarkTask("T99", "S99", "ENV1", "O99", ("QUALITY",), oracle_frozen=False, scoreable=True),
        )
        verdict = BenchmarkIntegrityCourt().evaluate(cohort)
        self.assertIn("T99", verdict.held_task_ids)
        self.assertNotIn("T99", verdict.scoreable_task_ids)

    def test_dominance_requires_minimum_market_composite_evidence(self):
        court = MarketCompositeCourt()
        cohort = tasks(20)
        candidate = observations("FUSE", "FUSE", causal=.95, quality=.95, wall=80, cost=80)
        baselines = (
            observations("LEADER_A", "INDIVIDUAL", causal=.90, quality=.90),
            observations("LEADER_B", "INDIVIDUAL", causal=.90, quality=.90),
            observations("COMPOSITE", "SYNTHETIC_MARKET_COMPOSITE", causal=.90, quality=.90),
        )
        verdict = court.compare(
            tasks=cohort,
            candidate_observations=candidate,
            baseline_observations=tuple(row for group in baselines for row in group),
            independent_judge_passed=True,
        )
        self.assertEqual(verdict.status, "MARKET_COMPOSITE_ADVANTAGE_PROVEN")
        self.assertEqual(set(verdict.dominated_baselines), {"LEADER_A", "LEADER_B", "COMPOSITE"})
        self.assertFalse(verdict.effect_authority_granted)

    def test_hard_floor_regression_blocks_superiority_even_if_faster(self):
        court = MarketCompositeCourt()
        cohort = tasks(20)
        candidate = observations("FUSE", "FUSE", causal=.99, quality=.99, floor=False, wall=1, cost=1)
        baseline_rows = tuple(
            row
            for group in (
                observations("A", "INDIVIDUAL"),
                observations("B", "INDIVIDUAL"),
                observations("C", "SYNTHETIC_MARKET_COMPOSITE"),
            )
            for row in group
        )
        verdict = court.compare(
            tasks=cohort,
            candidate_observations=candidate,
            baseline_observations=baseline_rows,
            independent_judge_passed=True,
        )
        self.assertEqual(verdict.status, "TARGET_NOT_PROVEN")
        self.assertIn("CANDIDATE_HARD_FLOOR_NONREGRESSION", verdict.missing_requirements)

    def test_tenx_is_not_declared_by_this_court(self):
        court = MarketCompositeCourt()
        self.assertFalse(hasattr(court, "tenx"))


if __name__ == "__main__":
    unittest.main()
