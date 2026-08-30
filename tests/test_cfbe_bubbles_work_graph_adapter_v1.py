from __future__ import annotations

import unittest

from federation.bubbles_frontier_hyperperformance import WorkCell
from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import (
    BubblesWorkNode,
    compile_work_graph,
    plan_bubbles_work_graph,
    shadow_place_bubbles_work,
)


class BubblesWorkGraphAdapterTests(unittest.TestCase):
    def _nodes(self):
        return (
            BubblesWorkNode(
                work_id="BHP-LEASE",
                capability="Current-State Lease",
                rail="STATE",
                next_action="prove freshness fail-closed",
                priority=1,
                role="PRIMARY",
            ),
            BubblesWorkNode(
                work_id="BHP-TRACE",
                capability="Unified Trace Spine",
                rail="STATE",
                next_action="prove trace lineage",
                dependencies=("BHP-LEASE",),
                priority=2,
                role="CHALLENGER",
            ),
            BubblesWorkNode(
                work_id="BHP-IDEM",
                capability="Universal Idempotency Envelope",
                rail="EFFECT_SAFETY",
                next_action="prove duplicate suppression",
                priority=3,
                role="PRIMARY",
            ),
        )

    def _cells(self):
        return (
            WorkCell("cell-a", ("provider-a", "zone-1"), capacity=2),
            WorkCell("cell-b", ("provider-b", "zone-2"), capacity=2),
            WorkCell("cell-c", ("provider-c", "zone-3"), capacity=2),
        )

    def test_adapter_reuses_cfbe_dependency_and_blocked_lane_isolation(self):
        receipt = plan_bubbles_work_graph(self._nodes())
        selected = {item.capability_id for item in receipt.selected}
        held = {item.capability_id: item for item in receipt.held}
        self.assertIn("BHP-LEASE", selected)
        self.assertIn("BHP-IDEM", selected)
        self.assertIn("DEPENDENCY_NOT_TERMINAL:BHP-LEASE", held["BHP-TRACE"].blockers)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.financial_effect_authorized)

    def test_completed_dependency_unlocks_challenger(self):
        receipt = plan_bubbles_work_graph(self._nodes(), completed_ids=("BHP-LEASE",))
        selected = {item.capability_id for item in receipt.selected}
        self.assertIn("BHP-TRACE", selected)
        self.assertIn("BHP-IDEM", selected)

    def test_existing_cfbe_wip_and_role_limits_remain_controlling(self):
        nodes = (
            BubblesWorkNode("A1", "primary", "A", "run A1", priority=1, role="PRIMARY"),
            BubblesWorkNode("A2", "challenger one", "A", "run A2", priority=2, role="CHALLENGER"),
            BubblesWorkNode("A3", "challenger two", "A", "run A3", priority=3, role="CHALLENGER"),
        )
        receipt = plan_bubbles_work_graph(nodes)
        self.assertEqual(2, len(receipt.selected))
        a3 = next(item for item in receipt.held if item.capability_id == "A3")
        self.assertTrue(
            "RAIL_WIP_LIMIT" in a3.blockers or "RAIL_CHALLENGER_LIMIT" in a3.blockers
        )

    def test_unknown_dependency_fails_before_scheduler(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_DEPENDENCY"):
            compile_work_graph(
                (
                    BubblesWorkNode(
                        "A1",
                        "bad dependency",
                        "A",
                        "never run",
                        dependencies=("MISSING",),
                    ),
                )
            )

    def test_shadow_cell_placement_is_deterministic_and_non_effectful(self):
        first = shadow_place_bubbles_work(self._nodes(), self._cells(), shard_width=2)
        second = shadow_place_bubbles_work(self._nodes(), self._cells(), shard_width=2)
        self.assertEqual(first.state, "SHADOW_READY")
        self.assertEqual(first.selected_work_ids, second.selected_work_ids)
        self.assertEqual(first.placement_digest, second.placement_digest)
        self.assertEqual(first.cell_occupancy, second.cell_occupancy)
        self.assertFalse(first.serving_route_changed)
        self.assertFalse(first.provider_effect_authorized)
        self.assertFalse(first.financial_effect_authorized)
        self.assertTrue(all(item.state == "ALLOCATED" for item in first.placements))

    def test_shadow_empty_cfbe_wave_remains_neutral_noop(self):
        receipt = shadow_place_bubbles_work(
            self._nodes(),
            (),
            active_ids=("BHP-LEASE", "BHP-IDEM"),
        )
        self.assertEqual(receipt.state, "SHADOW_READY")
        self.assertEqual(receipt.selected_work_ids, ())
        self.assertEqual(receipt.placements, ())
        self.assertEqual(receipt.cell_occupancy, ())
        self.assertEqual(receipt.remaining_capacity, ())
        self.assertEqual(receipt.backpressure_work_ids, ())
        self.assertFalse(receipt.serving_route_changed)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.financial_effect_authorized)

    def test_shadow_exclusion_preserves_cfbe_selection_but_changes_candidate_cells(self):
        receipt = shadow_place_bubbles_work(
            self._nodes(),
            self._cells(),
            shard_width=1,
            excluded_failure_domains=("provider-a",),
        )
        self.assertEqual(receipt.state, "SHADOW_READY")
        self.assertEqual(set(receipt.selected_work_ids), {"BHP-LEASE", "BHP-IDEM"})
        for placement in receipt.placements:
            self.assertNotIn("cell-a", placement.selected_cell_ids)
            self.assertIn("cell-a", placement.excluded_cell_ids)

    def test_shadow_insufficient_cell_diversity_holds_without_rewriting_serving_wave(self):
        cells = (
            WorkCell("cell-a", ("shared-provider", "zone-1")),
            WorkCell("cell-b", ("shared-provider", "zone-2")),
        )
        receipt = shadow_place_bubbles_work(self._nodes(), cells, shard_width=2)
        self.assertEqual(receipt.state, "SHADOW_HELD")
        self.assertEqual(set(receipt.selected_work_ids), {"BHP-LEASE", "BHP-IDEM"})
        self.assertFalse(receipt.serving_route_changed)
        self.assertTrue(
            all(
                item.state == "HOLD_INSUFFICIENT_CAPACITY_OR_FAILURE_DOMAIN_DIVERSITY"
                for item in receipt.placements
            )
        )

    def test_shadow_capacity_backpressure_preserves_serving_selection(self):
        cells = (WorkCell("cell-a", ("provider-a", "zone-1"), capacity=1),)
        receipt = shadow_place_bubbles_work(self._nodes(), cells, shard_width=1)
        self.assertEqual(receipt.state, "SHADOW_BACKPRESSURE")
        self.assertEqual(set(receipt.selected_work_ids), {"BHP-LEASE", "BHP-IDEM"})
        self.assertEqual(len(receipt.backpressure_work_ids), 1)
        self.assertEqual(receipt.cell_occupancy, (("cell-a", 1),))
        self.assertEqual(receipt.remaining_capacity, (("cell-a", 0),))
        self.assertEqual(receipt.saturated_cell_ids, ("cell-a",))
        self.assertFalse(receipt.serving_route_changed)
        self.assertFalse(receipt.provider_effect_authorized)

    def test_shadow_initial_occupancy_spills_work_without_route_change(self):
        cells = (
            WorkCell("cell-a", ("provider-a", "zone-1"), capacity=1),
            WorkCell("cell-b", ("provider-b", "zone-2"), capacity=2),
        )
        receipt = shadow_place_bubbles_work(
            self._nodes(),
            cells,
            shard_width=1,
            initial_occupancy={"cell-a": 1},
        )
        self.assertEqual(receipt.state, "SHADOW_READY")
        self.assertTrue(all(item.selected_cell_ids == ("cell-b",) for item in receipt.placements))
        self.assertFalse(receipt.serving_route_changed)


if __name__ == "__main__":
    unittest.main()
