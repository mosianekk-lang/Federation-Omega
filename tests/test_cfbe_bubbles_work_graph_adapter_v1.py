from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import (
    BubblesWorkNode,
    compile_work_graph,
    plan_bubbles_work_graph,
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


if __name__ == "__main__":
    unittest.main()
