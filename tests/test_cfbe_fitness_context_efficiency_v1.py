import unittest

from benchmarking.cfbe_omega.fitness_context_efficiency_v1 import (
    evaluate_retrieval_efficiency,
    run_bubbles_context_shadow,
)


class ContextEfficiencyCourtTests(unittest.TestCase):
    def test_retrieval_efficiency_preserves_accuracy(self):
        receipt = evaluate_retrieval_efficiency(
            broad_context_units=594,
            canonical_context_units=126,
            broad_calls=1,
            canonical_calls=1,
            source_accuracy_equal=True,
            privacy_expansion=False,
        )
        self.assertEqual(receipt.state, "POSITIVE_CONTEXT_SIGNAL")
        self.assertAlmostEqual(receipt.context_reduction_ratio, 0.787879, places=6)
        self.assertEqual(receipt.call_delta, 0)

    def test_bubbles_shadow_preserves_evidence_and_redacts(self):
        receipt = run_bubbles_context_shadow()
        self.assertEqual(receipt.state, "POSITIVE_BOUNDED_SHADOW")
        self.assertEqual(receipt.evidence_recall_ratio, 1.0)
        self.assertTrue(receipt.redaction_applied)
        self.assertGreater(receipt.context_reduction_ratio, 0.98)
        self.assertEqual(receipt.raw_context_action, "CHECKPOINT_COMPACT_REROUTE")
        self.assertEqual(receipt.bounded_context_action, "CONTINUE")
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.native_chat_interception_proven)


if __name__ == "__main__":
    unittest.main()
