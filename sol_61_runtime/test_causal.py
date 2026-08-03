from __future__ import annotations

import unittest

from causal import CausalDecisionEngine, CausalEdge, Intervention


class CausalDecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CausalDecisionEngine()
        self.engine.add_edge(CausalEdge("quota_exhaustion", "provider_errors", 0.9, 0.95, ("receipt-1",)))
        self.engine.add_edge(CausalEdge("provider_errors", "job_failures", 0.8, 0.9, ("receipt-2",)))
        self.engine.add_intervention(Intervention("symptom-retry", "job_failures", 0.2, 0.1, 0.4, 1.0))
        self.engine.add_intervention(Intervention("quota-failover", "quota_exhaustion", 0.85, 0.3, 0.15, 0.95))

    def test_upstream_and_symptom_rejection(self) -> None:
        self.assertEqual(self.engine.upstream_causes("job_failures"), {"provider_errors", "quota_exhaustion"})
        self.assertTrue(self.engine.is_symptom_only("symptom-retry", "job_failures"))
        self.assertFalse(self.engine.is_symptom_only("quota-failover", "job_failures"))

    def test_intervention_ranking(self) -> None:
        ranked = self.engine.rank_interventions("job_failures")
        self.assertEqual(ranked[0]["intervention"]["intervention_id"], "quota-failover")
        self.assertFalse(ranked[0]["symptom_only"])

    def test_bayesian_hypothesis_update(self) -> None:
        self.engine.register_hypothesis("quota_is_root_cause", 0.5)
        posterior = self.engine.update_hypothesis("quota_is_root_cause", 0.9, 0.2)
        self.assertGreater(posterior, 0.8)

    def test_counterfactual_and_effect_measurement(self) -> None:
        predicted = self.engine.counterfactual("quota-failover", 100)
        self.assertLess(predicted["predicted_after"], 20)
        measured = self.engine.measure_effect("quota-failover", 100, 10)
        self.assertTrue(measured["effective"])
        self.assertGreater(measured["actual_effect"], 0.8)


if __name__ == "__main__":
    unittest.main()
