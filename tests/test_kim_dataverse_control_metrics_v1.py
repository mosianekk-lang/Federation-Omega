from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_control_metrics_v1 import MissionEpisode, aggregate_institutional_metrics


class KimDataverseControlMetricsTests(unittest.TestCase):
    def test_metrics_capture_owner_burden_maintenance_recovery_chat_dependency_and_stalls(self) -> None:
        metrics = aggregate_institutional_metrics(
            (
                MissionEpisode("a", True, 1, 0, 2, 2, 1, 1, False, False),
                MissionEpisode("b", True, 1, 1, 1, 1, 1, 0, True, True),
            )
        )
        self.assertEqual(2, metrics.episode_count)
        self.assertEqual(1.0, metrics.verified_completion_rate)
        self.assertEqual(0.5, metrics.avoidable_owner_intervention_rate)
        self.assertEqual(1.0, metrics.maintenance_self_resolution_rate)
        self.assertEqual(0.5, metrics.recovery_self_resolution_rate)
        self.assertEqual(0.5, metrics.chat_dependency_rate)
        self.assertEqual(0.5, metrics.global_stall_rate)

    def test_zero_episode_metrics_fail_small_not_divide_by_zero(self) -> None:
        metrics = aggregate_institutional_metrics(())
        self.assertEqual(0, metrics.episode_count)
        self.assertEqual(0.0, metrics.verified_completion_rate)

    def test_invalid_self_resolution_counts_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            aggregate_institutional_metrics((MissionEpisode("a", True, 0, 0, 1, 2, 0, 0, False, False),))

    def test_duplicate_episode_id_fails_closed(self) -> None:
        episode = MissionEpisode("same", True, 0, 0, 0, 0, 0, 0, False, False)
        with self.assertRaises(ValueError):
            aggregate_institutional_metrics((episode, episode))


if __name__ == "__main__":
    unittest.main()
