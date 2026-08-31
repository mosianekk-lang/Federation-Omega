from __future__ import annotations

import unittest

from frontier_convergence.cfbe_fidelity_composite_router_v1 import (
    GoalEnvelope,
    PROOF_THRESHOLD,
    SURFACE_ORDER,
    benchmark_routes,
    qualification_suite,
    resolve_decomposed,
    resolve_unified,
)


class CFBEFidelityCompositeRouterTests(unittest.TestCase):
    def test_exact_four_surface_goal_resolves_one_bundle_with_four_independent_gates(self):
        receipt = resolve_unified(GoalEnvelope("G1"))
        self.assertEqual("ELIGIBLE_COMPOSITE_BUNDLE", receipt.state)
        self.assertEqual("CFBE-FIDELITY-READ-BUNDLE-V1", receipt.bundle_id)
        self.assertEqual(SURFACE_ORDER, tuple(lane.surface for lane in receipt.lanes))
        self.assertEqual(4, len({lane.authority_requirement for lane in receipt.lanes}))
        self.assertTrue(all(lane.proof_requirements for lane in receipt.lanes))
        self.assertTrue(all(lane.effect_class == "READ_ONLY" for lane in receipt.lanes))
        self.assertFalse(receipt.serving_route_changed)
        self.assertFalse(receipt.external_effects_authorized)
        self.assertFalse(receipt.stable_promotion_allowed)

    def test_missing_surface_or_weaker_proof_fails_closed(self):
        missing = resolve_unified(GoalEnvelope("G2", surfaces=("github", "drive", "gmail")))
        weak = resolve_unified(GoalEnvelope("G3", proof_threshold="STRUCTURAL_ONLY"))
        self.assertEqual("NO_ELIGIBLE_ROUTE", missing.state)
        self.assertIn("EXACT_FOUR_SURFACE_SET_REQUIRED", missing.rejection_reasons)
        self.assertEqual("NO_ELIGIBLE_ROUTE", weak.state)
        self.assertIn("PROOF_THRESHOLD_WEAKENED", weak.rejection_reasons)
        self.assertEqual(PROOF_THRESHOLD, GoalEnvelope("G4").proof_threshold)

    def test_unified_and_decomposed_paths_have_identical_semantic_receipts(self):
        for goal in qualification_suite():
            unified = resolve_unified(goal)
            decomposed = resolve_decomposed(goal)
            self.assertEqual(decomposed.state, unified.state)
            self.assertEqual(decomposed.semantic_digest, unified.semantic_digest)
            self.assertEqual(decomposed.rejection_reasons, unified.rejection_reasons)

    def test_benchmark_is_control_plane_only_and_preserves_claim_boundaries(self):
        receipt = benchmark_routes(rounds=3, iterations=10)
        self.assertEqual("CONTROL_PLANE_BENCHMARK_PASS", receipt["state"])
        self.assertTrue(receipt["semantic_parity"])
        self.assertEqual(len(qualification_suite()), receipt["suite_case_count"])
        self.assertGreater(receipt["unified_median_ns"], 0)
        self.assertGreater(receipt["decomposed_median_ns"], 0)
        self.assertFalse(receipt["provider_tool_calls_measured"])
        self.assertFalse(receipt["provider_latency_measured"])
        self.assertFalse(receipt["owner_value_measured"])
        self.assertFalse(receipt["stable_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
