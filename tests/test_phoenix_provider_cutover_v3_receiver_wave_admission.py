from __future__ import annotations

import io
import unittest


class FailureWinReceiverWaveAdmissionTests(unittest.TestCase):
    """Run focused receiver canaries inside the existing Airlock wildcard."""

    def test_caseforge_and_formation_failure_win_canaries_execute(self) -> None:
        suite = unittest.defaultTestLoader.loadTestsFromNames(
            (
                "tests.test_caseforge_failure_win_v2",
                "tests.test_formation_omega_failure_win_v2",
            )
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(2, result.testsRun, evidence)
        self.assertIn("test_caseforge_native_regression_planner_and_v2_canary", evidence)
        self.assertIn("test_formation_native_proof_and_surface_gate_then_v2_canary", evidence)


if __name__ == "__main__":
    unittest.main()
