from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_adversarial_validation import (
    FederationAdversarialValidator,
)


class FederationAdversarialValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = FederationAdversarialValidator()

    def test_all_nine_shortcut_attacks_are_vetoed(self) -> None:
        outcomes, receipt = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="adversarial-test-head",
        )
        self.assertEqual(9, len(outcomes))
        self.assertTrue(all(item.vetoed for item in outcomes))
        self.assertEqual("PASS", receipt.status)
        self.assertEqual(9, receipt.veto_count)
        self.assertEqual((), receipt.failed_cases)
        self.assertFalse(receipt.external_effect)
        self.assertEqual(64, len(receipt.receipt_sha256))

    def test_false_done_is_denied_with_internal_work(self) -> None:
        outcome = self.validator.false_done_with_internal_work()
        self.assertTrue(outcome.vetoed)
        self.assertIn("DONE_REQUIRES_ZERO_EXECUTABLE_INTERNAL_DEPENDENCIES", outcome.decision_code)

    def test_source_only_never_becomes_provider_verified(self) -> None:
        outcome = self.validator.source_only_provider_promotion()
        self.assertTrue(outcome.vetoed)
        self.assertIn("RUNTIME_UNBOUND", outcome.decision_code)

    def test_current_chat_cannot_self_attest_stage16(self) -> None:
        outcome = self.validator.current_chat_stage16_promotion()
        self.assertTrue(outcome.vetoed)
        self.assertEqual("CURRENT_CHAT_NONQUALIFYING", outcome.decision_code)

    def test_dominance_requires_provider_readback(self) -> None:
        outcome = self.validator.dominance_without_provider_readback()
        self.assertTrue(outcome.vetoed)
        self.assertIn("PROVIDER_READBACK_REQUIRED_FOR_DOMINANCE", outcome.decision_code)
        self.assertIn("OPERATIONAL_VERIFIED", outcome.proof_detail)

    def test_system_activity_does_not_prove_personal_actor(self) -> None:
        outcome = self.validator.system_activity_to_personal_attendance()
        self.assertTrue(outcome.vetoed)
        self.assertEqual("PERSONAL_ACTOR_REQUIRES_SEPARATE_IDENTITY_EVIDENCE", outcome.decision_code)

    def test_stale_base_and_phoenix_shortcuts_are_vetoed(self) -> None:
        stale = self.validator.force_merge_stale_branch()
        phoenix = self.validator.disable_phoenix_gate()
        self.assertTrue(stale.vetoed)
        self.assertEqual("RECUT_CURRENT_MAIN_REAPPLY_DELTA_RERUN", stale.decision_code)
        self.assertTrue(phoenix.vetoed)
        self.assertEqual("REPAIR_CODE_NOT_GATE_RERUN", phoenix.decision_code)

    def test_scheduler_label_is_not_execution_proof(self) -> None:
        outcome = self.validator.scheduler_label_as_execution()
        self.assertTrue(outcome.vetoed)
        self.assertEqual("QUARANTINE_REVERSE_REQUIRE_ACTUAL_RUNTIME", outcome.decision_code)

    def test_semantically_similar_proof_strings_have_different_digests(self) -> None:
        outcome = self.validator.semantic_receipt_equivalence()
        self.assertTrue(outcome.vetoed)
        self.assertEqual("DIGESTS_DIFFER", outcome.decision_code)

    def test_receipt_digest_is_deterministic(self) -> None:
        outcomes, first = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="same-head",
        )
        _, second = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="same-head",
        )
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertEqual(
            first.receipt_sha256,
            self.validator.receipt_digest_from_persisted_outcomes(
                system_id="FEDERATION_OMEGA",
                source_commit="same-head",
                outcomes=outcomes,
                status="PASS",
            ),
        )

    def test_v1_suite_is_bounded_to_federation_omega(self) -> None:
        with self.assertRaises(ValueError):
            self.validator.validate_suite(system_id="CHATBRIDGE", source_commit="head")
        with self.assertRaises(ValueError):
            self.validator.validate_suite(system_id="FEDERATION_OMEGA", source_commit="")


if __name__ == "__main__":
    unittest.main()
