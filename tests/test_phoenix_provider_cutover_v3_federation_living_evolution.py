from __future__ import annotations

import io
import unittest

from federation.living_state.evolution_intelligence import (
    EVOLUTION_INTELLIGENCE_SCHEMA, run_evolution_intelligence_canary,
)


class FederationLivingEvolutionAirlockTests(unittest.TestCase):
    def test_schema(self):
        self.assertEqual(EVOLUTION_INTELLIGENCE_SCHEMA, "FEDERATION-LIVING-EVOLUTION-INTELLIGENCE-V1")

    def test_focused_suite(self):
        suite = unittest.defaultTestLoader.discover("federation/living_state/tests", pattern="test_*.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        self.assertTrue(result.wasSuccessful(), "LIVING_EVOLUTION_REGRESSION_FAILED\n" + stream.getvalue())

    def test_canary(self):
        result = run_evolution_intelligence_canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 15)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)

    def test_truth_boundary(self):
        truth = run_evolution_intelligence_canary()["truth_boundary"]
        self.assertTrue(truth["counterfactual_is_topology_not_causation"])
        self.assertTrue(truth["attention_is_internal_budget_not_compute_execution"])
        self.assertTrue(truth["genome_candidates_are_shadow_only"])
        self.assertFalse(truth["external_effect_authority_created"])


if __name__ == "__main__":
    unittest.main()
