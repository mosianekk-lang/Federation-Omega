import unittest

from federation.bubbles_frontier_hyperperformance import (
    DeterministicAction,
    DeterministicResultCache,
    ReliabilityBudget,
    ReliabilityBudgetGovernor,
    WorkCell,
    WorkCellAllocator,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64
NOW = "2026-08-30T23:55:00+02:00"
FUTURE = "2026-08-31T01:00:00+02:00"


class WorkCellAllocatorTests(unittest.TestCase):
    def _cells(self):
        return (
            WorkCell("cell-a", ("provider-a", "zone-1"), capacity=4),
            WorkCell("cell-b", ("provider-b", "zone-2"), capacity=4),
            WorkCell("cell-c", ("provider-c", "zone-3"), capacity=4),
        )

    def test_allocation_is_deterministic(self):
        allocator = WorkCellAllocator()
        first = allocator.allocate("work-123", self._cells(), shard_width=2)
        second = allocator.allocate("work-123", self._cells(), shard_width=2)
        self.assertEqual(first.state, "ALLOCATED")
        self.assertEqual(first.selected_cell_ids, second.selected_cell_ids)
        self.assertEqual(first.allocation_digest, second.allocation_digest)

    def test_excluded_failure_domain_is_never_selected(self):
        decision = WorkCellAllocator().allocate(
            "work-123",
            self._cells(),
            shard_width=2,
            excluded_failure_domains=("provider-a",),
        )
        self.assertNotIn("cell-a", decision.selected_cell_ids)
        self.assertIn("cell-a", decision.excluded_cell_ids)

    def test_distinct_failure_domains_are_enforced(self):
        cells = (
            WorkCell("cell-a", ("provider-a", "zone-1")),
            WorkCell("cell-b", ("provider-a", "zone-2")),
            WorkCell("cell-c", ("provider-c", "zone-3")),
        )
        decision = WorkCellAllocator().allocate("work-456", cells, shard_width=2)
        self.assertEqual(decision.state, "ALLOCATED")
        selected = set(decision.selected_cell_ids)
        self.assertFalse({"cell-a", "cell-b"}.issubset(selected))

    def test_insufficient_diversity_fails_small(self):
        cells = (
            WorkCell("cell-a", ("shared", "zone-1")),
            WorkCell("cell-b", ("shared", "zone-2")),
        )
        decision = WorkCellAllocator().allocate("work-789", cells, shard_width=2)
        self.assertEqual(decision.state, "HOLD_INSUFFICIENT_FAILURE_DOMAIN_DIVERSITY")
        self.assertLess(len(decision.selected_cell_ids), 2)


class DeterministicResultCacheTests(unittest.TestCase):
    def _action(self, *, source=SHA_A, input_digest=SHA_B, environment=SHA_C, effect="NO_EFFECT"):
        return DeterministicAction(
            action="compile-mission-capsule",
            source_sha256=source,
            input_sha256=input_digest,
            environment_sha256=environment,
            proof_scope="BUBBLES_UNIT",
            fresh_until=FUTURE,
            effect_class=effect,
        )

    def test_exact_equivalent_action_hits_cache(self):
        cache = DeterministicResultCache()
        action = self._action()
        cache.record(
            action,
            result_ref="artifact://result-1",
            result_sha256=SHA_D,
            proof_refs=("proof://unit-1",),
            recorded_at=NOW,
            now=NOW,
        )
        decision = cache.lookup(action, now=NOW)
        self.assertEqual(decision.state, "HIT")
        self.assertTrue(decision.reuse)
        self.assertEqual(decision.result_sha256, SHA_D)

    def test_changed_identity_misses_cache(self):
        cache = DeterministicResultCache()
        original = self._action()
        cache.record(
            original,
            result_ref="artifact://result-1",
            result_sha256=SHA_D,
            proof_refs=("proof://unit-1",),
            recorded_at=NOW,
            now=NOW,
        )
        self.assertEqual(cache.lookup(self._action(source=SHA_B), now=NOW).state, "MISS")
        self.assertEqual(cache.lookup(self._action(input_digest=SHA_C), now=NOW).state, "MISS")
        self.assertEqual(cache.lookup(self._action(environment=SHA_D), now=NOW).state, "MISS")

    def test_effectful_work_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "DETERMINISTIC_CACHE_EFFECT_CLASS_PROHIBITED"):
            DeterministicResultCache().lookup(self._action(effect="EXTERNAL_WRITE"), now=NOW)

    def test_conflicting_same_key_result_is_rejected(self):
        cache = DeterministicResultCache()
        action = self._action()
        cache.record(
            action,
            result_ref="artifact://result-1",
            result_sha256=SHA_D,
            proof_refs=("proof://unit-1",),
            recorded_at=NOW,
            now=NOW,
        )
        with self.assertRaisesRegex(ValueError, "CACHE_RESULT_CONFLICT"):
            cache.record(
                action,
                result_ref="artifact://result-2",
                result_sha256=SHA_A,
                proof_refs=("proof://unit-2",),
                recorded_at=NOW,
                now=NOW,
            )


class ReliabilityBudgetGovernorTests(unittest.TestCase):
    def test_insufficient_window_is_held(self):
        decision = ReliabilityBudgetGovernor().evaluate(
            ReliabilityBudget(slo_success_ratio=0.99, observations=10, failures=0, min_observations=20)
        )
        self.assertEqual(decision.state, "HOLD_INSUFFICIENT_DATA")
        self.assertFalse(decision.promote)

    def test_healthy_window_is_reliability_eligible(self):
        decision = ReliabilityBudgetGovernor().evaluate(
            ReliabilityBudget(
                slo_success_ratio=0.99,
                observations=1000,
                failures=2,
                min_observations=100,
                max_burn_fraction_for_promotion=0.25,
            )
        )
        self.assertEqual(decision.state, "PROMOTION_ELIGIBLE_RELIABILITY_ONLY")
        self.assertTrue(decision.promote)
        self.assertAlmostEqual(decision.observed_failure_ratio, 0.002)
        self.assertAlmostEqual(decision.burn_fraction, 0.2)

    def test_burned_budget_holds_promotion(self):
        decision = ReliabilityBudgetGovernor().evaluate(
            ReliabilityBudget(
                slo_success_ratio=0.99,
                observations=1000,
                failures=8,
                min_observations=100,
                max_burn_fraction_for_promotion=0.25,
            )
        )
        self.assertEqual(decision.state, "HOLD_ERROR_BUDGET_BURN")
        self.assertFalse(decision.promote)
        self.assertAlmostEqual(decision.burn_fraction, 0.8)


if __name__ == "__main__":
    unittest.main()
