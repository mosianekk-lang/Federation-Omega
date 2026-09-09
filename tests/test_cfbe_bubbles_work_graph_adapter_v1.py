from __future__ import annotations

import unittest

from bubbles.ai_bot_multistream_host_v1 import run_host_canary
from bubbles.master_bible_portfolio_host_v1 import run_host_canary as run_portfolio_host_canary
from bubbles.fuse_gcp_cloud_service_host_v1 import run_host_canary as run_fuse_gcp_host_canary
from federation.bubbles_frontier_hyperperformance import WorkCell
from federation.fuse_mbmpc_pilf_closure_bridge_v1 import PStage
from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import (
    BubblesWorkNode,
    compile_work_graph,
    plan_bubbles_work_graph,
    shadow_place_bubbles_work,
)
from tests.test_bubbles_mbmpc_pilf_host_binding_v1 import (
    _contract as _of50_contract,
    _mission as _of50_mission,
    _of50_request,
    _runtime as _of50_runtime,
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

    def test_fuse_ai_bot_multistream_is_hosted_by_existing_bubbles_contract(self):
        receipt = run_host_canary(source_ref="test:bubbles-command-bus-contract")
        self.assertEqual("HOST_BOUND_VERIFIED", receipt["state"])
        self.assertTrue(receipt["host_binding_verified"])
        self.assertEqual(7, receipt["logical_bot_count"])
        self.assertEqual(0, receipt["provider_native_worker_count"])
        self.assertTrue(receipt["multipath_recovery_verified"])
        self.assertIn("SOURCE_PRIMARY", receipt["selected_wave"])
        self.assertFalse(receipt["provider_execution_attempted"])
        self.assertFalse(receipt["external_effect"])
        self.assertEqual("NONE", receipt["authority_delta"])
        self.assertIn(
            "SOURCE_PRIMARY:PRIMARY_ROUTE_PREDICATE_CHANGED",
            receipt["retryable_failures"],
        )

    def test_fuse_master_bible_portfolio_compiler_is_hosted_by_existing_bubbles_contract(self):
        receipt = run_portfolio_host_canary(source_ref="test:bubbles-command-bus-contract")
        self.assertEqual("HOST_BOUND_VERIFIED", receipt["state"])
        self.assertTrue(receipt["host_binding_verified"])
        portfolio = receipt["portfolio_receipt"]
        self.assertEqual(2, portfolio["active_required_mission_count"])
        self.assertEqual(1, portfolio["total_owner_only_debt"])
        self.assertFalse(portfolio["portfolio_complete_verified"])
        self.assertEqual("MISSION-ACTIVE-RUNTIME", portfolio["ready_wave"][0]["mission_id"])
        self.assertEqual("GAP-ACTIVE-EXECUTOR", portfolio["ready_wave"][0]["gap_id"])
        self.assertEqual("CAP-SHARED-TRACE", portfolio["shared_enablers"][0]["capability_id"])
        self.assertFalse(receipt["provider_execution_attempted"])
        self.assertFalse(receipt["external_effect"])
        self.assertEqual("NONE", receipt["authority_delta"])

    def test_current_canonical_of50_is_load_bearing_in_existing_bubbles_contract(self):
        result = _of50_runtime().finalize_mission_completion(
            _of50_mission(),
            spine_receipt=object(),
            production_contract=_of50_contract(),
            current_p_stage=PStage.P16_VALUE_OBSERVED,
            satisfied_terminal_predicates=("TP-FINAL",),
            production_stage_evidence_refs=("provider:production-stage:P16",),
            of50_request=_of50_request(),
        )
        self.assertEqual("MISSION_COMPLETION_VERIFIED", result["state"])
        self.assertTrue(result["mission_value_finalized"])
        self.assertTrue(result["of50_receipt"]["completion_verified"])
        self.assertTrue(result["truth_boundary"]["of50_current_canonical_completion_required"])
        self.assertTrue(result["truth_boundary"]["of50_and_mbmpc_pilf_finality_are_conjunctive"])

    def test_fuse_gcp_is_hosted_by_existing_bubbles_contract(self):
        receipt = run_fuse_gcp_host_canary(source_ref="test:bubbles-command-bus-contract")
        self.assertEqual("HOST_BOUND_VERIFIED", receipt["state"])
        self.assertTrue(receipt["host_binding_verified"])
        self.assertEqual("DIRECT_PROVIDER_READ", receipt["selected_route_id"])
        self.assertEqual(10, len(receipt["alpha_omega_stages"]))
        self.assertEqual(0, receipt["provider_native_worker_count"])
        self.assertFalse(receipt["provider_execution_attempted"])
        self.assertFalse(receipt["cloud_resource_mutation_attempted"])
        self.assertFalse(receipt["external_effect"])
        self.assertEqual("NONE", receipt["authority_delta"])


if __name__ == "__main__":
    unittest.main()
