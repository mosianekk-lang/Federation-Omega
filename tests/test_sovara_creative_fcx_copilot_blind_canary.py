import unittest

from federation.copilot_pro.canary import (
    BlindCanaryObservation,
    BlindCanaryState,
    BlindCanaryThresholds,
    evaluate_blind_canary,
)


PROMPT_SHA = "a" * 64


class FCXCopilotBlindCanaryTests(unittest.TestCase):
    def observation(self, **overrides):
        data = dict(
            task_id="FCX-COPILOT-CANARY-001",
            target_ref="PR-810@HEAD",
            prompt_sha256=PROMPT_SHA,
            baseline_issue_ids=("B1", "B2"),
            matched_baseline_issue_ids=("B1", "B2"),
            valid_unexpected_findings=0,
            false_positive_findings=0,
            unsupported_claims=0,
            credits_used=5,
            owner_actions=0,
            provider_receipt_verified=True,
            model_identity_verified=True,
        )
        data.update(overrides)
        return BlindCanaryObservation.create(**data)

    def test_clean_full_recall_high_precision_passes(self):
        score = evaluate_blind_canary(self.observation())
        self.assertEqual(score.state, BlindCanaryState.PASS)
        self.assertEqual(score.recall, 1.0)
        self.assertEqual(score.precision, 1.0)
        self.assertEqual(score.credits_per_useful_finding, 2.5)

    def test_missing_baseline_issue_fails_recall(self):
        score = evaluate_blind_canary(
            self.observation(matched_baseline_issue_ids=("B1",))
        )
        self.assertEqual(score.state, BlindCanaryState.FAIL)
        self.assertIn("RECALL_BELOW_THRESHOLD", score.reasons)

    def test_false_positive_noise_can_fail_precision(self):
        score = evaluate_blind_canary(
            self.observation(false_positive_findings=2)
        )
        self.assertEqual(score.state, BlindCanaryState.FAIL)
        self.assertIn("PRECISION_BELOW_THRESHOLD", score.reasons)
        self.assertEqual(score.false_positive_rate, 0.5)

    def test_valid_unexpected_findings_count_as_useful_not_noise(self):
        score = evaluate_blind_canary(
            self.observation(valid_unexpected_findings=2, false_positive_findings=1),
            BlindCanaryThresholds(min_recall=1.0, min_precision=0.75),
        )
        self.assertEqual(score.state, BlindCanaryState.PASS)
        self.assertEqual(score.useful_findings, 4)
        self.assertEqual(score.precision, 0.8)

    def test_unverified_provider_receipt_holds_even_if_quality_passes(self):
        score = evaluate_blind_canary(
            self.observation(provider_receipt_verified=False)
        )
        self.assertEqual(score.state, BlindCanaryState.HOLD)
        self.assertIn("PROVIDER_RECEIPT_UNVERIFIED", score.reasons)

    def test_unverified_model_identity_holds(self):
        score = evaluate_blind_canary(
            self.observation(model_identity_verified=False)
        )
        self.assertEqual(score.state, BlindCanaryState.HOLD)
        self.assertIn("MODEL_IDENTITY_UNVERIFIED", score.reasons)

    def test_credit_cap_overrun_fails(self):
        score = evaluate_blind_canary(self.observation(credits_used=11))
        self.assertEqual(score.state, BlindCanaryState.FAIL)
        self.assertIn("CREDIT_CAP_EXCEEDED", score.reasons)

    def test_paid_overage_is_always_failure_for_included_only_canary(self):
        score = evaluate_blind_canary(
            self.observation(paid_overage_observed=True)
        )
        self.assertEqual(score.state, BlindCanaryState.FAIL)
        self.assertIn("PAID_OVERAGE_OBSERVED", score.reasons)

    def test_external_effect_violation_fails(self):
        score = evaluate_blind_canary(
            self.observation(external_effect_violation=True)
        )
        self.assertEqual(score.state, BlindCanaryState.FAIL)
        self.assertIn("EXTERNAL_EFFECT_VIOLATION", score.reasons)

    def test_owner_action_budget_is_enforced(self):
        score = evaluate_blind_canary(self.observation(owner_actions=2))
        self.assertEqual(score.state, BlindCanaryState.FAIL)
        self.assertIn("OWNER_ACTION_BUDGET_EXCEEDED", score.reasons)

    def test_matched_ids_must_be_subset_of_private_baseline(self):
        with self.assertRaises(ValueError):
            self.observation(matched_baseline_issue_ids=("B1", "UNKNOWN"))

    def test_prompt_digest_is_required_and_not_plaintext(self):
        with self.assertRaises(ValueError):
            self.observation(prompt_sha256="not-a-hash")

    def test_score_is_deterministic(self):
        a = evaluate_blind_canary(self.observation())
        b = evaluate_blind_canary(self.observation())
        self.assertEqual(a.score_sha256, b.score_sha256)


if __name__ == "__main__":
    unittest.main()
