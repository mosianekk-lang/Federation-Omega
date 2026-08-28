from __future__ import annotations

import io
import unittest

from federation.living_state.future_intelligence import (
    FUTURE_INTELLIGENCE_SCHEMA, run_future_intelligence_canary,
)


class FederationLivingFutureAirlockTests(unittest.TestCase):
    def test_schema(self):
        self.assertEqual(FUTURE_INTELLIGENCE_SCHEMA, "FEDERATION-LIVING-FUTURE-INTELLIGENCE-V1")

    def test_focused_suite(self):
        suite = unittest.defaultTestLoader.discover("federation/living_state/tests", pattern="test_*.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        self.assertTrue(result.wasSuccessful(), "LIVING_FUTURE_REGRESSION_FAILED\n" + stream.getvalue())

    def test_canary(self):
        result = run_future_intelligence_canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 12)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)

    def test_truth_boundary(self):
        truth = run_future_intelligence_canary()["truth_boundary"]
        self.assertTrue(truth["scenario_is_simulation_not_prediction_fact"])
        self.assertTrue(truth["scenario_topology_is_not_causation"])
        self.assertTrue(truth["experiment_selection_does_not_execute_provider_actions"])
        self.assertTrue(truth["explanation_is_trace_not_new_proof"])
        self.assertTrue(truth["retirement_is_archive_first_and_non_deleting"])
        self.assertFalse(truth["external_effect_authority_created"])


if __name__ == "__main__":
    unittest.main()
