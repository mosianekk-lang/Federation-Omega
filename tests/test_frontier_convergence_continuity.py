import unittest

from frontier_convergence.continuity_adapter import (
    FederationExecutionContinuityAdapter,
    ToolPayloadCircuitBreaker,
)


class FrontierConvergenceContinuityTests(unittest.TestCase):
    def test_heavy_operation_requires_write_ahead_checkpoint(self):
        receipt = FederationExecutionContinuityAdapter.preflight(
            conversation_key="fc:test",
            checkpoint_readback_verified=True,
            namespace_bound=True,
            heavy_operation_pending=True,
        )
        assessment = receipt["assessment"]
        self.assertTrue(assessment["checkpoint_required"])
        self.assertFalse(assessment["new_heavy_work_allowed"])
        self.assertEqual("CHECKPOINT_THEN_CONTINUE", assessment["action"])

    def test_tool_timeout_requires_readback_even_when_stall_is_primary(self):
        receipt = FederationExecutionContinuityAdapter.diagnose_failure(
            {
                "message": "tool call timeout; no progress",
                "tool_inflight": True,
                "no_progress_seconds": 90,
                "active_directive": "complete frontier admission",
                "objective": "same-head production qualification",
                "last_proven_state": "SOURCE_READY",
                "last_completed_action": "port exact blobs",
                "next_pending_action": "read back provider/tool outcome",
                "tool_call_id": "tool-123",
                "conversation_id": "conv-1",
            }
        )
        candidate_classes = {item["failure_class"] for item in receipt["candidates"]}
        self.assertIn("STALL_TIMEOUT", candidate_classes)
        self.assertIn("TOOL_OR_CONNECTOR_FAILURE", candidate_classes)
        self.assertTrue(receipt["tool_outcome_readback_required"])
        self.assertEqual("READBACK_BEFORE_RETRY", receipt["retry_rule"])
        self.assertTrue(receipt["checkpoint"]["resume_token"])
        self.assertTrue(receipt["checkpoint"]["idempotency_key"])

    def test_large_tool_payload_is_bounded_and_failure_signal_is_preserved(self):
        raw = ("noise\n" * 5000) + "AssertionError: HASH_MISMATCH expected=x actual=y\n" + ("tail\n" * 5000)
        receipt = ToolPayloadCircuitBreaker.govern(raw, hard_char_limit=2048)
        self.assertEqual("BOUNDED_EXCEPTION_WINDOW", receipt.mode)
        self.assertLessEqual(receipt.returned_chars, 2085)
        self.assertGreater(receipt.omitted_chars, 0)
        self.assertIn("HASH_MISMATCH", receipt.text)
        self.assertIn("AssertionError", receipt.marker_hits)


if __name__ == "__main__":
    unittest.main()
