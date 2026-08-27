from __future__ import annotations

import io
import unittest


class FailureWinReceiverWave2AdmissionTests(unittest.TestCase):
    """Run focused source-native receiver canaries inside the existing Airlock wildcard."""

    def test_superior_sovara_reality_scientia_canaries_execute(self) -> None:
        suite = unittest.defaultTestLoader.loadTestsFromName(
            "tests.test_failure_win_receiver_wave2"
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(4, result.testsRun, evidence)
        self.assertIn("test_superior_logic_continuation_governor_then_v2", evidence)
        self.assertIn("test_sovara_cloudevent_contract_then_v2", evidence)
        self.assertIn("test_reality_guard_fault_manager_then_v2", evidence)
        self.assertIn("test_omega_scientia_falsification_then_v2", evidence)


if __name__ == "__main__":
    unittest.main()
