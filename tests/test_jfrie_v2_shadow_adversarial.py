from __future__ import annotations

import unittest

from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2_validation import (
    FULL_V2_PARITY,
    ValidationMode,
    run_adversarial_validation,
    run_shadow_validation,
)


SOURCE_REF = "github-main-f90bc2d4-jfrie-v2-core-contamination-assurance"
OBSERVED_AT = "2026-08-12T03:57:23+02:00"


class JfrieV2ShadowAdversarialTests(unittest.TestCase):
    def test_full_v2_parity_remains_false(self) -> None:
        self.assertFalse(FULL_V2_PARITY)

    def test_shadow_replay_suite_qualifies_without_external_effect(self) -> None:
        receipt = run_shadow_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        self.assertEqual(ValidationMode.SHADOW, receipt.mode)
        self.assertEqual(5, receipt.case_count)
        self.assertEqual(5, receipt.passed_count)
        self.assertEqual((), receipt.failed_case_ids)
        self.assertFalse(receipt.external_effect)
        self.assertTrue(receipt.qualifies)
        self.assertEqual(64, len(receipt.result_sha256))
        self.assertTrue(receipt.receipt_id.startswith("JFRIE-SHADOW-VALIDATION-"))

    def test_adversarial_replay_suite_qualifies_without_external_effect(self) -> None:
        receipt = run_adversarial_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        self.assertEqual(ValidationMode.ADVERSARIAL, receipt.mode)
        self.assertEqual(9, receipt.case_count)
        self.assertEqual(9, receipt.passed_count)
        self.assertEqual((), receipt.failed_case_ids)
        self.assertFalse(receipt.external_effect)
        self.assertTrue(receipt.qualifies)
        self.assertEqual(64, len(receipt.result_sha256))
        self.assertTrue(receipt.receipt_id.startswith("JFRIE-ADVERSARIAL-VALIDATION-"))

    def test_receipts_are_deterministic_for_identical_replay_inputs(self) -> None:
        first = run_shadow_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        second = run_shadow_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        self.assertEqual(first.result_sha256, second.result_sha256)
        self.assertEqual(first.receipt_id, second.receipt_id)

    def test_shadow_and_adversarial_receipts_are_distinct(self) -> None:
        shadow = run_shadow_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        adversarial = run_adversarial_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        self.assertNotEqual(shadow.result_sha256, adversarial.result_sha256)
        self.assertNotEqual(shadow.receipt_id, adversarial.receipt_id)


if __name__ == "__main__":
    unittest.main()
