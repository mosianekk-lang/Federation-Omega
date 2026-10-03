import unittest

from fuse_astra_semantic_kernel.cognition import (
    AdaptiveCognitionGovernor,
    CognitionTier,
    TaskSignals,
)


class CognitionGovernorTests(unittest.TestCase):
    def setUp(self):
        self.g = AdaptiveCognitionGovernor()

    def test_deterministic_fit_avoids_unnecessary_model_use(self):
        plan = self.g.plan(TaskSignals(deterministic_fit=0.98, uncertainty=0.05, novelty=0.05))
        self.assertEqual(plan.tier, CognitionTier.C0_DETERMINISTIC)
        self.assertEqual(plan.specialist_agents, 0)

    def test_high_risk_requires_stronger_verification(self):
        plan = self.g.plan(
            TaskSignals(
                uncertainty=0.7,
                novelty=0.7,
                failure_cost=0.95,
                irreversibility=0.9,
                contradiction_density=0.7,
            )
        )
        self.assertGreaterEqual(plan.verifier_count, 2)
        self.assertTrue(plan.adversarial_falsifier)
        self.assertTrue(plan.external_judge_required)

    def test_latency_pressure_does_not_suppress_high_risk_verification(self):
        plan = self.g.plan(
            TaskSignals(
                uncertainty=0.6,
                failure_cost=0.95,
                irreversibility=0.9,
                latency_pressure=1.0,
            )
        )
        self.assertGreaterEqual(plan.verifier_count, 2)
        self.assertTrue(plan.external_judge_required)

    def test_privacy_requirement_biases_local_first(self):
        plan = self.g.plan(TaskSignals(privacy_requirement=0.95, uncertainty=0.4, novelty=0.3))
        self.assertTrue(plan.require_local_first)

    def test_frontier_or_ensemble_reserved_for_complex_work(self):
        simple = self.g.plan(TaskSignals(uncertainty=0.2, novelty=0.2))
        hard = self.g.plan(
            TaskSignals(
                uncertainty=1.0,
                novelty=1.0,
                failure_cost=1.0,
                irreversibility=1.0,
                contradiction_density=1.0,
                tool_complexity=1.0,
            )
        )
        self.assertLess(simple.tier, hard.tier)
        self.assertEqual(hard.tier, CognitionTier.C5_ENSEMBLE_JUDGE)
        self.assertEqual(hard.reasoning_depth, "max")


if __name__ == "__main__":
    unittest.main()
