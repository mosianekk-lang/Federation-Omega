import unittest

from benchmarking.cfbe_omega.frontier_convergence_profile import (
    CURRENT_EVIDENCE_FACTOR,
    FrontierProof,
    compile_dimensions,
    evaluate,
)


class FrontierConvergenceBindingTests(unittest.TestCase):
    def test_current_internal_runtime_does_not_promote_provider_live(self):
        report = evaluate()
        self.assertEqual(CURRENT_EVIDENCE_FACTOR, 0.70)
        self.assertFalse(report.gemini_canary_verified)
        self.assertFalse(report.workspace_bidirectional_verified)
        self.assertFalse(report.production_qualified)
        self.assertNotEqual(report.leadership, "FRONTIER_LEADER")

    def test_provider_dimensions_start_at_claimed_factor(self):
        dims = {item.dimension_id: item for item in compile_dimensions()}
        self.assertEqual(dims["mission_sovereignty"].evidence_factor, 0.70)
        self.assertEqual(dims["gemini_provider"].evidence_factor, 0.30)
        self.assertEqual(dims["workspace_bidirectional"].evidence_factor, 0.30)

    def test_aggregate_sibling_claim_cannot_be_inherited_as_provider_live(self):
        proof = FrontierProof(
            proof_id="aggregate-sovara-status-only",
            state="PROVIDER_LIVE_INDEPENDENT_READBACK",
            receiver="gemini_provider",
            provider_native=False,
            independent_readback=False,
        )
        with self.assertRaises(ValueError):
            evaluate([proof])

    def test_exact_receiver_live_readback_promotes_only_that_receiver(self):
        gemini = FrontierProof(
            proof_id="gemini-native-receipt",
            state="PROVIDER_LIVE_INDEPENDENT_READBACK",
            receiver="gemini_provider",
            provider_native=True,
            independent_readback=True,
        )
        report = evaluate([gemini])
        self.assertTrue(report.gemini_canary_verified)
        self.assertFalse(report.workspace_bidirectional_verified)
        self.assertFalse(report.production_qualified)

    def test_production_qualification_requires_both_live_receivers(self):
        proofs = [
            FrontierProof(
                proof_id="gemini-native-receipt",
                state="PROVIDER_LIVE_INDEPENDENT_READBACK",
                receiver="gemini_provider",
                provider_native=True,
                independent_readback=True,
            ),
            FrontierProof(
                proof_id="workspace-native-receipt",
                state="PROVIDER_LIVE_INDEPENDENT_READBACK",
                receiver="workspace_bidirectional",
                provider_native=True,
                independent_readback=True,
            ),
        ]
        report = evaluate(proofs)
        self.assertTrue(report.gemini_canary_verified)
        self.assertTrue(report.workspace_bidirectional_verified)
        self.assertTrue(report.production_qualified)
        # Independent replication is still separately required for a leader claim.
        self.assertNotEqual(report.leadership, "FRONTIER_LEADER")

    def test_duplicate_receiver_proofs_fail_closed(self):
        proof = FrontierProof("p1", "CONTROL_PLANE_OR_SOURCE_ONLY", "gemini_provider")
        duplicate = FrontierProof("p2", "CONTROL_PLANE_OR_SOURCE_ONLY", "gemini_provider")
        with self.assertRaises(ValueError):
            evaluate([proof, duplicate])


if __name__ == "__main__":
    unittest.main()
