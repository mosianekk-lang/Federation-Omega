from __future__ import annotations

import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BeaconPilotAdmissionTests(unittest.TestCase):
    def test_beacon_pilot_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_ecertify_pilot_scorecard.py")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(6, result.testsRun, evidence)
        self.assertIn("test_document_bytes_transmission_fails_zero_possession_pilot", evidence)
        self.assertIn("test_success_claim_fails_closed_until_all_metrics_exist", evidence)

    def test_scorecard_and_guard_are_present(self) -> None:
        self.assertTrue((ROOT / "evidenceops" / "ecertify_za" / "PILOT_SCORECARD.json").is_file())
        self.assertTrue((ROOT / "evidenceops" / "ecertify_za" / "pilot_scorecard.py").is_file())


if __name__ == "__main__":
    unittest.main()
