from __future__ import annotations

import unittest

from evidenceops.ecertify_za.pilot_scorecard import PilotScorecard


class BeaconPilotScorecardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scorecard = PilotScorecard.load()

    def _passing(self):
        return {
            "receipt_issue_success_rate": 1.0,
            "receipt_verify_success_rate": 1.0,
            "tampered_receipt_rejection_rate": 1.0,
            "document_bytes_transmitted": False,
            "statutory_claim_violation_count": 0,
            "task_completion_rate": 0.95,
            "median_latency_ms": 900,
            "error_rate": 0.01,
            "user_confusion_rate": 0.05,
            "support_escalation_rate": 0.05,
        }

    def test_no_observations_means_no_pilot_result(self) -> None:
        result = self.scorecard.evaluate({})
        self.assertFalse(result["pilot_result_available"])
        self.assertFalse(result["pilot_success"])
        self.assertGreater(len(result["missing_metrics"]), 0)

    def test_passing_observations_meet_acceptance(self) -> None:
        result = self.scorecard.evaluate(self._passing())
        self.assertTrue(result["pilot_result_available"])
        self.assertTrue(result["pilot_success"])
        self.assertEqual([], result["failed_metrics"])

    def test_document_bytes_transmission_fails_zero_possession_pilot(self) -> None:
        values = self._passing()
        values["document_bytes_transmitted"] = True
        result = self.scorecard.evaluate(values)
        self.assertFalse(result["pilot_success"])
        self.assertIn("document_bytes_transmitted", result["failed_metrics"])

    def test_statutory_claim_violation_is_fatal_to_acceptance(self) -> None:
        values = self._passing()
        values["statutory_claim_violation_count"] = 1
        result = self.scorecard.evaluate(values)
        self.assertFalse(result["pilot_success"])
        self.assertIn("statutory_claim_violation_count", result["failed_metrics"])

    def test_success_claim_fails_closed_until_all_metrics_exist(self) -> None:
        with self.assertRaisesRegex(ValueError, "PILOT_RESULT_UNAVAILABLE_MISSING_METRICS"):
            self.scorecard.claim_pilot_success({"receipt_issue_success_rate": 1.0})

    def test_safe_claim_remains_non_statutory(self) -> None:
        claim = self.scorecard.payload["safe_public_claim"].lower()
        self.assertIn("not statutory certification", claim)
        self.assertIn("not", claim)


if __name__ == "__main__":
    unittest.main()
