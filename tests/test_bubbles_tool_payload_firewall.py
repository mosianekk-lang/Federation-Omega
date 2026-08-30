import unittest

from federation.bubbles_tool_payload_firewall import (
    DiagnosticExtractor,
    ToolPayloadBudget,
    ToolPayloadFirewall,
    ToolPayloadObservation,
)


class ToolPayloadFirewallTests(unittest.TestCase):
    def test_small_text_payload_is_admitted(self):
        decision = ToolPayloadFirewall().evaluate(
            ToolPayloadObservation(
                tool_name="github.status",
                payload_chars=2_000,
                line_count=40,
            )
        )
        self.assertTrue(decision.admit_raw)
        self.assertEqual(decision.action, "ADMIT_RAW")
        self.assertFalse(decision.diagnostic_required)

    def test_large_workflow_log_is_extracted_before_hydration(self):
        firewall = ToolPayloadFirewall(
            ToolPayloadBudget(max_raw_chars=10_000, max_raw_lines=100, max_diagnostic_chars=4_000, max_diagnostic_lines=50)
        )
        decision = firewall.evaluate(
            ToolPayloadObservation(
                tool_name="github.workflow.logs",
                payload_chars=45_000,
                line_count=900,
                content_kind="workflow_log",
            )
        )
        self.assertFalse(decision.admit_raw)
        self.assertEqual(decision.action, "EXTRACT_BOUNDED_DIAGNOSTIC")
        self.assertIn("RAW_CHAR_BUDGET", decision.reasons)
        self.assertIn("RAW_LINE_BUDGET", decision.reasons)
        self.assertIn("HEAVY_CONTENT_PREEMPTION", decision.reasons)

    def test_sensitive_hint_never_admits_raw(self):
        decision = ToolPayloadFirewall().evaluate(
            ToolPayloadObservation(
                tool_name="provider.debug",
                payload_chars=500,
                line_count=10,
                contains_sensitive_hint=True,
            )
        )
        self.assertFalse(decision.admit_raw)
        self.assertEqual(decision.action, "REDACT_AND_EXTRACT_DIAGNOSTIC")


class DiagnosticExtractorTests(unittest.TestCase):
    def test_failure_lines_and_tail_are_bounded_and_redacted(self):
        payload = "\n".join(
            [f"normal line {i}" for i in range(50)]
            + [
                "step failed with exit code 1",
                "API_KEY=super-secret-value",
                "Authorization: Bearer abc.def.ghi",
                "Traceback: test failed",
            ]
            + [f"tail line {i}" for i in range(30)]
        )
        budget = ToolPayloadBudget(
            max_raw_chars=10_000,
            max_raw_lines=200,
            max_diagnostic_chars=800,
            max_diagnostic_lines=20,
            tail_lines=5,
        )
        capsule = DiagnosticExtractor(budget).extract(payload)
        self.assertIn("failed with exit code 1", capsule.excerpt)
        self.assertIn("API_KEY=[REDACTED]", capsule.excerpt)
        self.assertIn("Bearer [REDACTED]", capsule.excerpt)
        self.assertNotIn("super-secret-value", capsule.excerpt)
        self.assertNotIn("abc.def.ghi", capsule.excerpt)
        self.assertLessEqual(len(capsule.excerpt), 800)
        self.assertLessEqual(capsule.selected_lines, 20)
        self.assertTrue(capsule.redaction_applied)
        self.assertTrue(capsule.truncated)
        self.assertEqual(len(capsule.raw_sha256), 64)

    def test_same_payload_has_same_hash(self):
        extractor = DiagnosticExtractor()
        first = extractor.extract("ERROR one\nend")
        second = extractor.extract("ERROR one\nend")
        self.assertEqual(first.raw_sha256, second.raw_sha256)


if __name__ == "__main__":
    unittest.main()
