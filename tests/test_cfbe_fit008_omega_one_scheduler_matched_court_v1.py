import unittest

from benchmarking.cfbe_omega.omega_one_scheduler_matched_court_v1 import run_fit008_court


class Fit008OmegaOneSchedulerCourtTests(unittest.TestCase):
    def test_frozen_corpus_surfaces_non_dominant_tradeoff_without_promotion(self):
        receipt = run_fit008_court(source_head_sha="0" * 40)
        self.assertEqual(receipt.profile_count, 4)
        self.assertEqual(receipt.task_count_per_profile, 48)
        self.assertEqual(receipt.best_fixed_policy, "FIXED_2")
        self.assertEqual(receipt.candidate_completion_time_units, 9000.0)
        self.assertEqual(receipt.best_fixed_completion_time_units, 9600.0)
        self.assertEqual(receipt.candidate_retry_work, 18)
        self.assertEqual(receipt.best_fixed_retry_work, 0)
        self.assertEqual(receipt.completion_time_ratio, 0.9375)
        self.assertEqual(receipt.retry_work_delta, 18)
        self.assertEqual(receipt.verdict, "TRADEOFF_NON_DOMINANT")
        self.assertFalse(receipt.candidate_dominates)
        self.assertTrue(receipt.all_tasks_completed)
        self.assertTrue(receipt.fairness_guardrail_pass)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_promotion_allowed)
        self.assertFalse(receipt.owner_value_proven)
        self.assertEqual(receipt.next_action, "TEST_RETRY_COST_AWARE_OR_WORKLOAD_CONDITIONAL_ROUTING")

    def test_receipt_is_deterministic(self):
        left = run_fit008_court(source_head_sha="1" * 40)
        right = run_fit008_court(source_head_sha="1" * 40)
        self.assertEqual(left, right)
        self.assertEqual(len(left.receipt_sha256), 64)


if __name__ == "__main__":
    unittest.main()
