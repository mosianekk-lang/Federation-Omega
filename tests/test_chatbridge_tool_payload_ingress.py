import unittest

from federation.chatbridge_tool_payload_ingress import ChatBridgeToolPayloadIngress


class ChatBridgeToolPayloadIngressTests(unittest.TestCase):
    @staticmethod
    def _heavy_payload() -> str:
        lines = [f"INFO worker={index:04d} payload={'x' * 80}" for index in range(1800)]
        lines[900] = (
            "ERROR provider request failed returncode=17 "
            "Authorization: Bearer CANARYSECRET0123456789"
        )
        lines[-2] = "INFO cleanup complete"
        lines[-1] = "conclusion=failure exit code 17"
        return "\n".join(lines)

    def test_heavy_payload_is_compacted_redacted_and_failure_complete(self) -> None:
        raw = self._heavy_payload()
        result = ChatBridgeToolPayloadIngress().ingest(
            tool_name="github.workflow_job_log",
            payload=raw,
            content_kind="workflow_log",
            contains_sensitive_hint=True,
        )
        receipt = result.receipt
        self.assertFalse(receipt.raw_admitted)
        self.assertTrue(receipt.diagnostic_required)
        self.assertEqual("BOUNDED_DIAGNOSTIC", receipt.state)
        self.assertGreater(receipt.reduction_percent, 90.0)
        self.assertLessEqual(receipt.bounded_chars, 6_000)
        self.assertLessEqual(receipt.bounded_lines, 80)
        self.assertTrue(receipt.redaction_applied)
        self.assertIn("ERROR provider request failed returncode=17", result.bounded_payload)
        self.assertIn("Bearer [REDACTED]", result.bounded_payload)
        self.assertNotIn("CANARYSECRET0123456789", result.bounded_payload)
        self.assertEqual(0, receipt.external_effects)

    def test_small_non_sensitive_payload_remains_available(self) -> None:
        raw = "status=success\nselected_tests=8\nfailures=0"
        result = ChatBridgeToolPayloadIngress().ingest(
            tool_name="proofos.summary",
            payload=raw,
            content_kind="text",
        )
        self.assertTrue(result.receipt.raw_admitted)
        self.assertFalse(result.receipt.diagnostic_required)
        self.assertEqual(raw, result.bounded_payload)
        self.assertEqual(0.0, result.receipt.reduction_percent)

    def test_small_sensitive_payload_is_never_raw_admitted(self) -> None:
        raw = "ERROR auth failed Authorization: Bearer SHOULD_NOT_SURVIVE"
        result = ChatBridgeToolPayloadIngress().ingest(
            tool_name="provider.stderr",
            payload=raw,
            content_kind="provider_log",
            contains_sensitive_hint=True,
        )
        self.assertFalse(result.receipt.raw_admitted)
        self.assertIn("Bearer [REDACTED]", result.bounded_payload)
        self.assertNotIn("SHOULD_NOT_SURVIVE", result.bounded_payload)

    def test_receipt_contains_hash_lineage_not_raw_payload(self) -> None:
        raw = self._heavy_payload()
        result = ChatBridgeToolPayloadIngress().ingest(
            tool_name="provider.stderr",
            payload=raw,
            content_kind="provider_log",
            contains_sensitive_hint=True,
        )
        rendered = str(result.receipt.to_dict())
        self.assertNotIn("CANARYSECRET0123456789", rendered)
        self.assertEqual(64, len(result.receipt.raw_sha256))
        self.assertEqual(64, len(result.receipt.bounded_sha256))
        self.assertEqual(64, len(result.receipt.receipt_sha256))


if __name__ == "__main__":
    unittest.main()
