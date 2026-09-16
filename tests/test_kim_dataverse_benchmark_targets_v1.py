from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_benchmark_targets_v1 import benchmark_targets


class KimDataverseBenchmarkTargetTests(unittest.TestCase):
    def test_level7_targets_remove_chat_dependency_and_global_stalls(self) -> None:
        by_metric = {item.metric: item for item in benchmark_targets()}
        self.assertEqual(0.0, by_metric["chat_dependency_rate"].level7_target)
        self.assertEqual(0.0, by_metric["global_stall_rate"].level7_target)

    def test_level7_owner_interruption_target_is_five_percent_or_less(self) -> None:
        by_metric = {item.metric: item for item in benchmark_targets()}
        self.assertLessEqual(by_metric["avoidable_owner_interruption_rate"].level7_target, 0.05)

    def test_level7_maintenance_and_recovery_targets_are_high(self) -> None:
        by_metric = {item.metric: item for item in benchmark_targets()}
        self.assertGreaterEqual(by_metric["maintenance_self_resolution_rate"].level7_target, 0.95)
        self.assertGreaterEqual(by_metric["recovery_self_resolution_rate"].level7_target, 0.95)


if __name__ == "__main__":
    unittest.main()
