import unittest

from bubbles.chat_governor_omega3.frontier_evolution_v4 import (
    IndependentHarnessGate,
    InterveningChange,
    InterveningChangeReconciler,
    ParetoPolicyOptimizer,
    PolicyOutcome,
    TrajectoryCrystallizer,
    TrajectoryObservation,
    frontier_evolution_v4_receipt,
)


class CrystallizerTests(unittest.TestCase):
    @staticmethod
    def observations(count=6, *, success=True, proof_valid=True, effect_class="READ_ONLY"):
        return [
            TrajectoryObservation(
                trajectory_id=f"t-{i}",
                tool_sequence=("retrieve", "verify", "synthesize"),
                precondition_schema_sha256="a" * 64,
                context_fingerprint=f"ctx-{i % 3}",
                effect_class=effect_class,
                proof_axes=("source", "semantic_readback"),
                success=success,
                proof_valid=proof_valid,
                latency_ms=100 + i,
                cost=0.10,
                owner_burden=0.0,
            )
            for i in range(count)
        ]

    def test_repeated_proven_route_crystallizes_only_to_non_authorized_candidate(self):
        candidate = TrajectoryCrystallizer(min_runs=6, min_context_diversity=3).compile(self.observations())
        self.assertIsNotNone(candidate)
        self.assertEqual("CANDIDATE_DETERMINISTIC_SKILL", candidate.state)
        self.assertFalse(candidate.auto_execution_authorized)
        self.assertFalse(candidate.source_admission_authorized)
        self.assertEqual(6, candidate.observed_runs)
        self.assertEqual(3, candidate.context_diversity)

    def test_any_failed_or_unproven_run_blocks_crystallization(self):
        rows = self.observations()
        bad = list(rows)
        bad[0] = TrajectoryObservation(
            trajectory_id="bad",
            tool_sequence=rows[0].tool_sequence,
            precondition_schema_sha256=rows[0].precondition_schema_sha256,
            context_fingerprint=rows[0].context_fingerprint,
            effect_class=rows[0].effect_class,
            proof_axes=rows[0].proof_axes,
            success=False,
            proof_valid=True,
            latency_ms=1,
            cost=0,
            owner_burden=0,
        )
        self.assertIsNone(TrajectoryCrystallizer(min_runs=6, min_context_diversity=3).compile(bad))

    def test_effectful_route_remains_effect_gated_candidate(self):
        candidate = TrajectoryCrystallizer(min_runs=6, min_context_diversity=3).compile(
            self.observations(effect_class="CONSEQUENTIAL_EFFECT")
        )
        self.assertEqual("CANDIDATE_EFFECT_GATED", candidate.state)
        self.assertFalse(candidate.auto_execution_authorized)


class ParetoTests(unittest.TestCase):
    def test_proof_violating_and_low_sample_policies_are_rejected(self):
        result = ParetoPolicyOptimizer(min_success_lower_bound=0.8, min_sample_size=30).evaluate(
            [
                PolicyOutcome("good", 0.95, 0, 100, 1.0, 0.1, 100),
                PolicyOutcome("proof-bad", 0.99, 1, 1, 0.1, 0.0, 100),
                PolicyOutcome("small", 0.99, 0, 1, 0.1, 0.0, 5),
            ]
        )
        self.assertEqual(("good",), result.frontier)
        self.assertEqual({"proof-bad", "small"}, set(result.rejected))
        self.assertFalse(result.auto_promotion_authorized)

    def test_dominated_policy_drops_from_frontier(self):
        result = ParetoPolicyOptimizer().evaluate(
            [
                PolicyOutcome("a", 0.95, 0, 100, 1.0, 0.1, 100),
                PolicyOutcome("b", 0.95, 0, 120, 1.2, 0.2, 100),
                PolicyOutcome("c", 0.96, 0, 110, 0.8, 0.1, 100),
            ]
        )
        self.assertNotIn("b", result.frontier)
        self.assertIn("a", result.frontier)
        self.assertIn("c", result.frontier)


class IndependentHarnessTests(unittest.TestCase):
    def test_high_risk_requires_three_independent_principals(self):
        gate = IndependentHarnessGate()
        denied = gate.decide(
            risk_class="R4_CORE",
            author_principal="author",
            test_principal="author",
            review_principal="review",
        )
        self.assertFalse(denied.allow)
        allowed = gate.decide(
            risk_class="R4_CORE",
            author_principal="author",
            test_principal="tester",
            review_principal="reviewer",
        )
        self.assertTrue(allowed.allow)

    def test_lower_risk_records_independence_without_blocking(self):
        decision = IndependentHarnessGate().decide(
            risk_class="R1",
            author_principal="same",
            test_principal="same",
            review_principal="same",
        )
        self.assertTrue(decision.allow)
        self.assertFalse(decision.independent_test_author)


class InterveningChangeTests(unittest.TestCase):
    def test_exact_path_overlap_requires_conflict_court(self):
        decision = InterveningChangeReconciler().decide(
            candidate_paths=["a.py", "b.py"],
            candidate_dependency_tags=["proofos"],
            intervening_changes=[InterveningChange("b.py", ("other",))],
        )
        self.assertEqual("CONFLICT_COURT_REQUIRED", decision.action)
        self.assertEqual(("b.py",), decision.exact_path_conflicts)
        self.assertFalse(decision.wholesale_rollback_authorized)

    def test_disjoint_path_with_shared_dependency_requires_semantic_revalidation(self):
        decision = InterveningChangeReconciler().decide(
            candidate_paths=["feature.py"],
            candidate_dependency_tags=["proofos", "chatgov"],
            intervening_changes=[InterveningChange("different.py", ("proofos",))],
        )
        self.assertEqual("SEMANTIC_REVALIDATION_REQUIRED", decision.action)
        self.assertEqual(("proofos",), decision.semantic_dependency_conflicts)

    def test_disjoint_independent_change_allows_one_late_reanchor(self):
        decision = InterveningChangeReconciler().decide(
            candidate_paths=["feature.py"],
            candidate_dependency_tags=["chatgov"],
            intervening_changes=[InterveningChange("gmail.py", ("gmail",))],
        )
        self.assertEqual("LATE_REANCHOR_SAFE", decision.action)


class ReceiptTests(unittest.TestCase):
    def test_v4_never_self_promotes(self):
        receipt = frontier_evolution_v4_receipt()
        self.assertFalse(receipt.skill_promotion_authorized)
        self.assertFalse(receipt.source_merge_authorized)
        self.assertFalse(receipt.effect_authorized)
        self.assertIn("PROVEN_TRAJECTORY_TO_SKILL_CANDIDATE_CRYSTALLIZATION", receipt.capabilities)


if __name__ == "__main__":
    unittest.main()
