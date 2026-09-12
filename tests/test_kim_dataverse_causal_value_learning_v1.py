from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_causal_value_learning_v1 import (
    CausalHypothesis,
    HypothesisState,
    StrategyOutcome,
    compare_strategies,
    update_hypothesis,
)


class KimDataverseCausalValueLearningTests(unittest.TestCase):
    def test_observed_pair_can_be_value_candidate_only_without_quality_or_reliability_regression(self) -> None:
        champion = StrategyOutcome(
            "episode-1", "prime", "obj", True, 0.8, 0.9, 1000, 3, 12, ("proof:a",), True
        )
        challenger = StrategyOutcome(
            "episode-1", "market", "obj", True, 0.82, 0.91, 950, 2.5, 5, ("proof:b",), True
        )
        result = compare_strategies(champion, challenger)
        self.assertTrue(result.observed_pair)
        self.assertTrue(result.value_candidate)
        self.assertLess(result.owner_minutes_delta, 0)

    def test_shadow_or_synthetic_pair_never_becomes_owner_value_candidate(self) -> None:
        champion = StrategyOutcome(
            "episode-1", "prime", "obj", True, 0.8, 0.9, 1000, 3, 12, (), False, True
        )
        challenger = StrategyOutcome(
            "episode-1", "market", "obj", True, 0.9, 0.95, 900, 2, 1, (), False, True
        )
        result = compare_strategies(champion, challenger)
        self.assertFalse(result.observed_pair)
        self.assertFalse(result.value_candidate)

    def test_quality_regression_blocks_value_candidate_even_if_owner_time_improves(self) -> None:
        champion = StrategyOutcome(
            "episode-1", "prime", "obj", True, 0.9, 0.9, 1000, 3, 12, ("proof:a",), True
        )
        challenger = StrategyOutcome(
            "episode-1", "market", "obj", True, 0.85, 0.95, 800, 2, 1, ("proof:b",), True
        )
        result = compare_strategies(champion, challenger)
        self.assertFalse(result.value_candidate)

    def test_matched_episode_and_objective_are_required(self) -> None:
        champion = StrategyOutcome(
            "episode-1", "prime", "obj", True, 0.8, 0.9, 1000, 3, 12, ("proof:a",), True
        )
        challenger = StrategyOutcome(
            "episode-2", "market", "obj", True, 0.9, 0.95, 800, 2, 1, ("proof:b",), True
        )
        with self.assertRaises(ValueError):
            compare_strategies(champion, challenger)

    def test_observed_outcome_requires_proof(self) -> None:
        champion = StrategyOutcome(
            "episode-1", "prime", "obj", True, 0.8, 0.9, 1000, 3, 12, (), True
        )
        challenger = StrategyOutcome(
            "episode-1", "market", "obj", True, 0.9, 0.95, 800, 2, 1, ("proof:b",), True
        )
        with self.assertRaises(ValueError):
            compare_strategies(champion, challenger)

    def test_causal_hypothesis_distinguishes_support_falsification_and_conflict(self) -> None:
        hypothesis = CausalHypothesis("h1", "provider latency reduction", "lower latency", "latency unchanged")
        supported = update_hypothesis(hypothesis, supporting_refs=("proof:s",))
        self.assertEqual(HypothesisState.SUPPORTED, supported.state)
        falsified = update_hypothesis(hypothesis, falsifying_refs=("proof:f",))
        self.assertEqual(HypothesisState.FALSIFIED, falsified.state)
        unresolved = update_hypothesis(hypothesis, supporting_refs=("proof:s",), falsifying_refs=("proof:f",))
        self.assertEqual(HypothesisState.UNRESOLVED, unresolved.state)

    def test_strategy_receipt_is_deterministic(self) -> None:
        champion = StrategyOutcome(
            "episode-1", "prime", "obj", True, 0.8, 0.9, 1000, 3, 12, ("proof:a",), True
        )
        challenger = StrategyOutcome(
            "episode-1", "market", "obj", True, 0.82, 0.91, 950, 2.5, 5, ("proof:b",), True
        )
        self.assertEqual(compare_strategies(champion, challenger).receipt, compare_strategies(champion, challenger).receipt)


if __name__ == "__main__":
    unittest.main()
