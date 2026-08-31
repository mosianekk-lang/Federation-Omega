from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.mission_execution_adapter_v1 import shadow_compile_mission_execution
from federation.bubbles_frontier_hyperperformance import WorkCell
from federation.mission_ir import MissionIR
from frontier_convergence.mission_ir_golden_path_shadow import build_receipt


class MissionIRProviderPolicyBindingTests(unittest.TestCase):
    def _mission(self) -> MissionIR:
        return MissionIR(
            mission_id="M1",
            objective="Bound provider route.",
            domain="TEST",
            outcome_contract="One shadow receipt.",
            source_frontier="main@test",
            privacy_class="PUBLIC",
            rights_state="NOT_APPLICABLE",
            effect_class="BOUNDED_EFFECT",
            authority_requirements=("CANVA_BOUNDED_CREATE",),
            proof_requirements=("READBACK",),
            provider_allowlist=("CANVA",),
        ).normalized()

    def _nodes(self):
        return (BubblesWorkNode("W1", "work", "TEST", "shadow"),)

    def _cells(self):
        return (
            WorkCell("canva", ("canva", "region-a")),
            WorkCell("gemini", ("gemini", "region-b")),
            WorkCell("unknown", ("unknown", "region-c")),
        )

    def test_provider_allowlist_filters_cell_candidates_fail_closed(self):
        receipt = shadow_compile_mission_execution(
            self._mission(),
            self._nodes(),
            self._cells(),
            cell_provider_aliases={"canva": "CANVA", "gemini": "GEMINI"},
        )
        self.assertEqual("SHADOW_READY", receipt.cell_shadow_state)
        self.assertEqual(("gemini", "unknown"), receipt.provider_policy_excluded_cell_ids)
        self.assertEqual(("unknown",), receipt.provider_policy_unmapped_cell_ids)
        selected = {
            cell_id
            for placement in receipt.cell_placements
            for cell_id in placement.selected_cell_ids
        }
        self.assertEqual({"canva"}, selected)
        self.assertFalse(receipt.provider_effect_authorized)

    def test_no_eligible_provider_cell_holds_without_changing_serving(self):
        receipt = shadow_compile_mission_execution(
            self._mission(),
            self._nodes(),
            self._cells(),
            cell_provider_aliases={"gemini": "GEMINI"},
        )
        self.assertEqual("SHADOW_HELD_PROVIDER_POLICY", receipt.cell_shadow_state)
        self.assertFalse(receipt.serving_route_changed)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertEqual((), receipt.cell_placements)


class GoldenPathShadowCertificationTests(unittest.TestCase):
    def test_receipt_proves_semantics_without_inventing_runtime_value(self):
        receipt = build_receipt(certification_source_sha="test-sha")
        self.assertTrue(receipt["semantic_pass"])
        self.assertEqual(["SC-PLAN"], receipt["selected_work_ids"])
        self.assertEqual(["cell-adobe", "cell-gemini"], receipt["provider_policy_excluded_cell_ids"])
        selected = {
            cell_id
            for placement in receipt["cell_placements"]
            for cell_id in placement["selected_cell_ids"]
        }
        self.assertEqual({"cell-canva"}, selected)
        self.assertFalse(receipt["provider_effect_authorized"])
        self.assertFalse(receipt["financial_effect_authorized"])
        self.assertFalse(receipt["publication_authorized"])
        self.assertEqual(0, receipt["external_effects"])
        self.assertFalse(receipt["stable_promotion_allowed"])
        self.assertFalse(receipt["runtime_metrics"]["observed_runtime_comparison_proven"])
        self.assertIsNone(receipt["runtime_metrics"]["tool_call_delta"])
        self.assertIsNone(receipt["runtime_metrics"]["owner_intervention_delta"])

    def test_structural_comparison_is_improvement_candidate_not_runtime_claim(self):
        receipt = build_receipt(certification_source_sha="test-sha")
        self.assertLess(receipt["structural_deltas"]["control_surfaces"], 0)
        self.assertLess(receipt["structural_deltas"]["constraint_join_edges"], 0)
        self.assertLess(receipt["structural_deltas"]["proof_requirement_locations"], 0)
        self.assertEqual(
            "CONTROL_STRUCTURE_NOT_RUNTIME_TELEMETRY",
            receipt["legacy_structural_profile"]["evidence_mode"],
        )


class FourSurfaceCompositeRouterQualificationTests(unittest.TestCase):
    def test_composite_bundle_keeps_four_surface_authority_and_proof_gates(self):
        from frontier_convergence.cfbe_fidelity_composite_router_v1 import (
            GoalEnvelope,
            SURFACE_ORDER,
            resolve_unified,
        )

        receipt = resolve_unified(GoalEnvelope("HOSTED-COMPOSITE-1"))
        self.assertEqual("ELIGIBLE_COMPOSITE_BUNDLE", receipt.state)
        self.assertEqual(SURFACE_ORDER, tuple(lane.surface for lane in receipt.lanes))
        self.assertEqual(4, len({lane.authority_requirement for lane in receipt.lanes}))
        self.assertTrue(all(lane.proof_requirements for lane in receipt.lanes))
        self.assertTrue(all(lane.effect_class == "READ_ONLY" for lane in receipt.lanes))
        self.assertFalse(receipt.serving_route_changed)
        self.assertFalse(receipt.external_effects_authorized)
        self.assertFalse(receipt.stable_promotion_allowed)

    def test_composite_and_decomposed_receipts_are_semantically_identical(self):
        from frontier_convergence.cfbe_fidelity_composite_router_v1 import (
            qualification_suite,
            resolve_decomposed,
            resolve_unified,
        )

        for goal in qualification_suite():
            unified = resolve_unified(goal)
            decomposed = resolve_decomposed(goal)
            self.assertEqual(decomposed.state, unified.state)
            self.assertEqual(decomposed.semantic_digest, unified.semantic_digest)
            self.assertEqual(decomposed.rejection_reasons, unified.rejection_reasons)


if __name__ == "__main__":
    unittest.main()

