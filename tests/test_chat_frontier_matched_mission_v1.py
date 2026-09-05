from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.chat_frontier_matched_mission_v1 import run_matched_mission


class ChatFrontierMatchedMissionTests(unittest.TestCase):
    def test_candidate_clears_two_x_work_target_without_proof_regression(self):
        result = run_matched_mission()
        self.assertEqual("DETERMINISTIC_MECHANISM_LEVEL_MATCHED_MISSION", result.benchmark_kind)
        self.assertEqual(10, result.baseline_execution_units)
        self.assertEqual(2, result.candidate_execution_units)
        self.assertGreaterEqual(result.execution_unit_reduction_fraction, 0.50)
        self.assertGreaterEqual(result.execution_efficiency_factor, 2.0)
        self.assertEqual(400, result.baseline_context_chars)
        self.assertEqual(200, result.candidate_context_chars)
        self.assertGreater(result.modeled_tail_release_reduction_fraction, 0.50)
        self.assertTrue(result.two_x_waste_target_met)
        self.assertTrue(result.proof_quality_non_degraded)
        self.assertFalse(result.provider_effect_authorized)
        self.assertFalse(result.production_performance_proven)
        self.assertFalse(result.provider_native_performance_proven)
        self.assertEqual(64, len(result.result_sha256))


if __name__ == "__main__":
    unittest.main()
