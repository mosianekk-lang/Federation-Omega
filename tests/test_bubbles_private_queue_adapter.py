import json
import unittest

from bubbles.private_queue_adapter import (
    PrivateQueueError,
    PrivateQueueRequest,
    build_queue_row,
    command_fingerprint,
    interpret_queue_row,
    proof_receipt,
)


class BubblesPrivateQueueAdapterTests(unittest.TestCase):
    def request(self, **overrides):
        values = dict(
            command_id="BUBBLES-TEST-001",
            created_at="2026-08-12T19:37:04+02:00",
            command="GAS_SELFTEST",
            target="",
            payload={"source": "BUBBLES_CHATGPT_CONTROL_PLANE", "nonDestructive": True},
            dry_run=True,
            risk="LOW",
            notes="dry-run canary",
        )
        values.update(overrides)
        return PrivateQueueRequest(**values)

    def test_selftest_row_uses_pending_and_never_populates_approval(self):
        row = build_queue_row(self.request())
        self.assertEqual("PENDING", row[2])
        self.assertEqual("GAS_SELFTEST", row[3])
        self.assertEqual("", row[6])
        self.assertIs(row[7], True)
        self.assertEqual("LOW", row[8])

    def test_secret_or_approval_fields_are_rejected(self):
        with self.assertRaises(PrivateQueueError):
            build_queue_row(self.request(payload={"approvalKey": "forbidden"}))
        with self.assertRaises(PrivateQueueError):
            build_queue_row(self.request(payload={"nested": {"api_key": "forbidden"}}))

    def test_selftest_cannot_request_live_mutation(self):
        with self.assertRaises(PrivateQueueError):
            build_queue_row(self.request(dry_run=False))

    def test_selftest_cannot_have_external_target(self):
        with self.assertRaises(PrivateQueueError):
            build_queue_row(self.request(target="https://example.invalid"))

    def test_current_live_approval_failure_becomes_authority_held(self):
        row = list(build_queue_row(self.request()))
        row[2] = "ERROR"
        row[9] = json.dumps(
            {
                "status": "ERROR",
                "commandId": "BUBBLES-TEST-001",
                "command": "GAS_SELFTEST",
                "error": "APPROVAL_KEY_REQUIRED_OR_INVALID",
            }
        )
        row[10] = "2026-08-12T17:52:38.331Z"
        decision = interpret_queue_row(row)
        self.assertEqual("AUTHORITY_HELD", decision.state)
        self.assertFalse(decision.retry_allowed)
        self.assertIn("Do not retry with a raw approval key", decision.reason)

    def test_done_semantic_success_requires_processed_at(self):
        row = list(build_queue_row(self.request()))
        row[2] = "DONE"
        row[9] = json.dumps({"status": "OK", "version": "v2.2"})
        decision = interpret_queue_row(row)
        self.assertEqual("PROOF_FAILED", decision.state)

        row[10] = "2026-08-12T18:00:00.000Z"
        decision = interpret_queue_row(row)
        self.assertEqual("SUCCESS", decision.state)

    def test_pending_state_is_not_retried_by_adapter(self):
        decision = interpret_queue_row(list(build_queue_row(self.request())))
        self.assertEqual("PENDING", decision.state)
        self.assertFalse(decision.retry_allowed)

    def test_command_fingerprint_is_deterministic(self):
        request = self.request()
        self.assertEqual(command_fingerprint(request), command_fingerprint(request))
        self.assertEqual(64, len(command_fingerprint(request)))

    def test_receipt_never_claims_broader_provider_authority(self):
        row = list(build_queue_row(self.request()))
        row[2] = "ERROR"
        row[9] = json.dumps({"status": "ERROR", "error": "APPROVAL_KEY_REQUIRED_OR_INVALID"})
        row[10] = "2026-08-12T17:52:38.331Z"
        receipt = proof_receipt(self.request(), row)
        self.assertEqual("AUTHORITY_HELD", receipt["state"])
        self.assertIn("never proves broader Google Cloud", receipt["truth_boundary"])
        self.assertNotIn("approvalKey", json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
