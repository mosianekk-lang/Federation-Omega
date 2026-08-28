from __future__ import annotations

import io
import unittest

from federation.living_state.world_model import AUTHORITY_CEILING, SCHEMA, run_living_fabric_canary


class FederationLivingStateAirlockBridgeTests(unittest.TestCase):
    """Bind living-state focused regressions to the existing admitted Airlock."""

    def test_authority_and_schema_boundary(self):
        self.assertEqual(SCHEMA, "FEDERATION-LIVING-STATE-EVOLUTION-FABRIC-V1")
        self.assertEqual(AUTHORITY_CEILING, "A1_INTERNAL")

    def test_full_focused_suite(self):
        suite = unittest.defaultTestLoader.discover(
            "federation/living_state/tests",
            pattern="test_*.py",
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2, failfast=False).run(suite)
        self.assertTrue(result.wasSuccessful(), "LIVING_STATE_REGRESSION_FAILED\n" + stream.getvalue())

    def test_canary_is_effect_free(self):
        result = run_living_fabric_canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 26)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)

    def test_truth_boundary_blocks_autonomy_inflation(self):
        truth = run_living_fabric_canary()["truth_boundary"]
        self.assertFalse(truth["continuous_unattended_runtime_claimed"])
        self.assertFalse(truth["hidden_cross_chat_access_claimed"])
        self.assertFalse(truth["provider_authority_inferred"])
        self.assertFalse(truth["synthetic_metrics_are_provider_performance"])
        self.assertFalse(truth["living_fabric_executes_external_effects"])


if __name__ == "__main__":
    unittest.main()
