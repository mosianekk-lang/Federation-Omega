from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_value_retention_v1 import CapabilityValueWindow, RetentionAction, evaluate_value_retention


class KimDataverseValueRetentionTests(unittest.TestCase):
    def test_clean_observed_value_window_retains_capability(self) -> None:
        decision = evaluate_value_retention((CapabilityValueWindow("cap", 10, 10, 10, 0, 0, 0, True),))[0]
        self.assertEqual(RetentionAction.RETAIN, decision.action)
        self.assertTrue(decision.value_proven)
        self.assertFalse(decision.rollback_authorized)

    def test_regression_with_rollback_is_candidate_not_auto_rollback(self) -> None:
        decision = evaluate_value_retention((CapabilityValueWindow("cap", 10, 9, 10, 1, 0, 0, True),))[0]
        self.assertEqual(RetentionAction.ROLLBACK_CANDIDATE, decision.action)
        self.assertFalse(decision.rollback_authorized)

    def test_insufficient_observed_value_is_held(self) -> None:
        decision = evaluate_value_retention((CapabilityValueWindow("cap", 3, 3, 3, 0, 0, 0, True),))[0]
        self.assertEqual(RetentionAction.VALUE_HOLD, decision.action)
        self.assertFalse(decision.value_proven)

    def test_verified_success_count_cannot_exceed_observed_episodes(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_value_retention((CapabilityValueWindow("cap", 1, 2, 1, 0, 0, 0, True),))


if __name__ == "__main__":
    unittest.main()
