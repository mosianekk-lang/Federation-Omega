from __future__ import annotations

import unittest

from sovara.creative.supply_chain import CreativeDiscoveryGraph, PerformanceObservation


def observation(
    oid: str,
    asset: str,
    reward: float,
    sequence: int,
    *,
    cohort: str = "cohort-1",
    channel: str = "instagram",
    attribution: str = "provider:analytics-1",
    fresh: bool = True,
) -> PerformanceObservation:
    return PerformanceObservation(
        oid,
        asset,
        ("luxury",),
        reward,
        sequence,
        mission_id="mission-1",
        cohort_id=cohort,
        channel=channel,
        attribution_ref=attribution,
        observed_at=f"2026-09-01T10:0{sequence}:00+02:00",
        fresh=fresh,
    )


class SovaraCreativePerformanceLearningHardeningTests(unittest.TestCase):
    def graph(self) -> CreativeDiscoveryGraph:
        return CreativeDiscoveryGraph(
            min_observations=2,
            min_distinct_assets=2,
            mission_id="mission-1",
            cohort_id="cohort-1",
            channel="instagram",
        )

    def test_unbound_graph_is_descriptive_only_even_with_repeated_signal(self) -> None:
        graph = CreativeDiscoveryGraph(min_observations=2)
        graph.observe(PerformanceObservation("p1", "a1", ("luxury",), 1.0, 1))
        graph.observe(PerformanceObservation("p2", "a2", ("luxury",), 1.0, 2))
        receipt = graph.receipt()
        self.assertFalse(receipt.context_bound)
        self.assertTrue(receipt.descriptive_only)
        self.assertFalse(receipt.learning_ready)
        self.assertEqual(0, receipt.qualified_observation_count)

    def test_context_bound_graph_requires_fresh_attributed_observations(self) -> None:
        graph = self.graph()
        graph.observe(observation("p1", "a1", 0.8, 1, attribution=""))
        graph.observe(observation("p2", "a2", 0.7, 2, fresh=False))
        receipt = graph.receipt()
        self.assertEqual(2, receipt.eligible_observation_count)
        self.assertEqual(0, receipt.qualified_observation_count)
        self.assertFalse(receipt.learning_ready)

    def test_two_fresh_attributed_distinct_assets_can_become_learning_ready(self) -> None:
        graph = self.graph()
        graph.observe(observation("p1", "a1", 0.8, 1))
        graph.observe(observation("p2", "a2", 0.6, 2))
        receipt = graph.receipt()
        self.assertTrue(receipt.context_bound)
        self.assertFalse(receipt.descriptive_only)
        self.assertEqual(2, receipt.qualified_observation_count)
        self.assertTrue(receipt.learning_ready)
        self.assertEqual(("luxury",), tuple(row.tag for row in receipt.recommendations))
        self.assertEqual(0.7, receipt.recommendations[0].score)
        self.assertEqual(2, receipt.recommendations[0].distinct_asset_count)

    def test_same_asset_repeated_does_not_satisfy_distinct_asset_gate(self) -> None:
        graph = self.graph()
        graph.observe(observation("p1", "a1", 0.8, 1))
        graph.observe(observation("p2", "a1", 0.6, 2))
        receipt = graph.receipt()
        self.assertFalse(receipt.learning_ready)
        self.assertEqual(2, receipt.qualified_observation_count)
        self.assertEqual((), receipt.recommendations)

    def test_cross_cohort_or_channel_observation_is_rejected_not_aggregated(self) -> None:
        graph = self.graph()
        with self.assertRaisesRegex(ValueError, "cohort context"):
            graph.observe(observation("p1", "a1", 0.8, 1, cohort="cohort-2"))
        with self.assertRaisesRegex(ValueError, "channel context"):
            graph.observe(observation("p2", "a2", 0.7, 2, channel="youtube"))


if __name__ == "__main__":
    unittest.main()
