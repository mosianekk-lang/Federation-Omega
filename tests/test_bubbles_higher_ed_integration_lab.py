from __future__ import annotations

import unittest

from bubbles.higher_ed_integration_lab import HigherEdIntegrationLab, IntegrationEvent, run_reference_scenario


class HigherEdIntegrationLabTests(unittest.TestCase):
    def test_reference_scenario_spans_five_systems_and_generates_lineage(self) -> None:
        events = (
            IntegrationEvent("E1", "S001", "CRM", "APPLICATION_SUBMITTED", "SUBMITTED", "BSc IT"),
            IntegrationEvent("E2", "S001", "CRM", "ADMISSION_ACCEPTED", "ACCEPTED"),
            IntegrationEvent("E3", "S001", "SIS", "REGISTERED", "REGISTERED"),
            IntegrationEvent("E4", "S001", "LMS", "LEARNING_ACTIVE", "ACTIVE"),
            IntegrationEvent("E5", "S001", "LMS", "ASSESSMENT_COMPLETED", "COMPLETED"),
            IntegrationEvent("E6", "S001", "ERP", "FEE_BALANCE_UPDATED", "UPDATED", amount=1250.0),
            IntegrationEvent("E7", "S001", "SIS", "GRADUATED", "GRADUATED"),
        )
        result = run_reference_scenario(events)
        self.assertEqual(7, len(result["receipts"]))
        self.assertGreater(len(result["lineage"]["lineage"]), 0)
        self.assertEqual(1, result["kpis"]["graduated"])
        self.assertEqual(1, result["kpis"]["completed_assessments"])
        self.assertEqual(1250.0, result["kpis"]["outstanding_amount_synthetic"])
        self.assertEqual(64, len(result["lineage"]["sha256"]))

    def test_idempotent_replay_returns_same_receipt_without_duplicate_lineage(self) -> None:
        lab = HigherEdIntegrationLab()
        event = IntegrationEvent("E1", "S001", "SIS", "REGISTERED", "REGISTERED", "MBA")
        first = lab.process(event)
        lineage_count = len(lab.lineage_receipt()["lineage"])
        second = lab.process(event)
        self.assertEqual(first.payload_sha256, second.payload_sha256)
        self.assertEqual(lineage_count, len(lab.lineage_receipt()["lineage"]))

    def test_idempotency_conflict_fails_closed(self) -> None:
        lab = HigherEdIntegrationLab()
        lab.process(IntegrationEvent("E1", "S001", "SIS", "REGISTERED", "REGISTERED", "MBA"))
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            lab.process(IntegrationEvent("E1", "S001", "SIS", "REGISTERED", "REGISTERED", "BSc IT"))

    def test_retry_recovers_without_dead_letter(self) -> None:
        lab = HigherEdIntegrationLab()
        receipt = lab.process(
            IntegrationEvent("E1", "S001", "SIS", "REGISTERED", "REGISTERED", "BSc IT"),
            fail_first_attempt=True,
        )
        self.assertEqual("DONE", receipt.target_state)
        self.assertEqual(2, receipt.attempt_count)
        self.assertFalse(receipt.dead_lettered)
        self.assertEqual("REGISTERED", receipt.semantic_readback)

    def test_unknown_system_and_unsupported_event_fail_closed(self) -> None:
        lab = HigherEdIntegrationLab()
        with self.assertRaisesRegex(ValueError, "Unknown source system"):
            lab.process(IntegrationEvent("E1", "S001", "EMAIL", "REGISTERED", "REGISTERED"))
        with self.assertRaisesRegex(ValueError, "Unsupported event_type"):
            lab.process(IntegrationEvent("E2", "S001", "SIS", "UNSUPPORTED", "X"))

    def test_negative_financial_amount_is_rejected(self) -> None:
        lab = HigherEdIntegrationLab()
        with self.assertRaisesRegex(ValueError, "amount cannot be negative"):
            lab.process(IntegrationEvent("E1", "S001", "ERP", "FEE_BALANCE_UPDATED", "UPDATED", amount=-1.0))

    def test_truth_boundaries_prevent_real_university_overclaim(self) -> None:
        result = run_reference_scenario((IntegrationEvent("E1", "S001", "CRM", "APPLICATION_SUBMITTED", "SUBMITTED"),))
        self.assertIn("synthetic", result["safe_claim"].casefold())
        self.assertIn("deployed at a university", result["forbidden_claims"])
        self.assertIn("not real institutional", result["kpis"]["truth_boundary"].casefold())


if __name__ == "__main__":
    unittest.main()
