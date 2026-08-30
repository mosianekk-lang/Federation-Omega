import unittest

from federation.copilot_pro import (
    CopilotCreditBudget,
    CopilotDispatchState,
    CopilotRole,
    CopilotRunObservation,
    CopilotTaskSpec,
    WriteMode,
    compile_task_envelope,
    evaluate_dispatch,
    to_cfbe_route,
    usage_receipt,
)


class FCXCopilotProAdapterTests(unittest.TestCase):
    def budget(self, *, used=100, total=1500, paid=False, paid_cap=0, enforced=False, verified=True):
        return CopilotCreditBudget(
            plan_id="COPILOT_PRO",
            cycle_id="2026-08",
            included_total_credits=total,
            included_used_credits=used,
            snapshot_verified=verified,
            additional_paid_usage_allowed=paid,
            additional_paid_credit_cap=paid_cap,
            provider_budget_enforced=enforced,
        )

    def task(self, **overrides):
        data = dict(
            task_id="FCX-COPILOT-TASK-001",
            role=CopilotRole.REVIEWER,
            objective="Review the bounded source change for defects and proof gaps.",
            path_scope=("federation/orchestration",),
            privacy_class="INTERNAL_SAFE",
            write_mode=WriteMode.READ_ONLY,
            task_credit_cap=25,
            requested_model="AUTO",
            source_pr_authorized=False,
        )
        data.update(overrides)
        return CopilotTaskSpec.create(**data)

    def test_envelope_is_deterministic(self):
        a = compile_task_envelope(self.task())
        b = compile_task_envelope(self.task())
        self.assertEqual(a.envelope_sha256, b.envelope_sha256)
        self.assertTrue(a.no_secret_payload)
        self.assertTrue(a.no_provider_effect)

    def test_secret_and_case_data_fail_closed(self):
        for privacy in ("PRIVATE_CASE", "SENSITIVE_IDENTITY", "SECRET"):
            decision = evaluate_dispatch(self.task(privacy_class=privacy), self.budget())
            self.assertEqual(decision.state, CopilotDispatchState.HOLD_PRIVACY)
            self.assertFalse(decision.eligible)

    def test_unverified_budget_snapshot_holds(self):
        decision = evaluate_dispatch(self.task(), self.budget(verified=False))
        self.assertEqual(decision.state, CopilotDispatchState.HOLD_CREDIT_BUDGET)
        self.assertIn("CREDIT_BUDGET_SNAPSHOT_UNVERIFIED", decision.reasons)

    def test_task_cap_must_fit_included_credits_when_paid_overage_disabled(self):
        decision = evaluate_dispatch(self.task(task_credit_cap=150), self.budget(used=1400))
        self.assertEqual(decision.state, CopilotDispatchState.HOLD_CREDIT_BUDGET)
        self.assertIn("TASK_CAP_EXCEEDS_INCLUDED_REMAINING", decision.reasons)

    def test_paid_overage_requires_provider_budget_enforcement(self):
        decision = evaluate_dispatch(
            self.task(task_credit_cap=150),
            self.budget(used=1400, paid=True, paid_cap=100, enforced=False),
        )
        self.assertEqual(decision.state, CopilotDispatchState.HOLD_CREDIT_BUDGET)
        self.assertIn("PAID_OVERAGE_REQUIRES_PROVIDER_BUDGET_ENFORCEMENT", decision.reasons)

    def test_builder_requires_branch_pr_authority(self):
        task = self.task(
            role=CopilotRole.BUILDER,
            write_mode=WriteMode.BRANCH_PR,
            source_pr_authorized=False,
        )
        decision = evaluate_dispatch(task, self.budget())
        self.assertEqual(decision.state, CopilotDispatchState.HOLD_AUTHORITY)
        self.assertIn("BRANCH_PR_AUTHORITY_REQUIRED", decision.reasons)

    def test_builder_with_branch_pr_authority_can_be_ready_on_included_credits(self):
        task = self.task(
            role=CopilotRole.BUILDER,
            write_mode=WriteMode.BRANCH_PR,
            source_pr_authorized=True,
        )
        decision = evaluate_dispatch(task, self.budget())
        self.assertEqual(decision.state, CopilotDispatchState.READY_INCLUDED_CREDITS)
        self.assertTrue(decision.eligible)
        self.assertFalse(decision.paid_overage_authorized)

    def test_non_builder_cannot_receive_write_mode(self):
        decision = evaluate_dispatch(self.task(write_mode=WriteMode.BRANCH_PR), self.budget())
        self.assertEqual(decision.state, CopilotDispatchState.HOLD_AUTHORITY)
        self.assertIn("NON_BUILDER_MUST_BE_READ_ONLY", decision.reasons)

    def test_provider_or_consequential_effect_is_held(self):
        decision = evaluate_dispatch(self.task(provider_effect=True), self.budget())
        self.assertEqual(decision.state, CopilotDispatchState.HOLD_AUTHORITY)
        self.assertIn("CONSEQUENTIAL_OR_PROVIDER_EFFECT_NOT_AUTHORISED", decision.reasons)

    def test_gemini_challenger_requires_gemini_request(self):
        task = self.task(role=CopilotRole.GEMINI_CHALLENGER, requested_model="AUTO")
        decision = evaluate_dispatch(task, self.budget())
        self.assertEqual(decision.state, CopilotDispatchState.HOLD_MODEL_CONTRACT)
        self.assertIn("GEMINI_CHALLENGER_REQUIRES_GEMINI_MODEL_REQUEST", decision.reasons)

    def test_gemini_challenger_can_be_ready_with_explicit_model_request(self):
        task = self.task(role=CopilotRole.GEMINI_CHALLENGER, requested_model="Gemini 3.1 Pro")
        decision = evaluate_dispatch(task, self.budget())
        self.assertEqual(decision.state, CopilotDispatchState.READY_INCLUDED_CREDITS)
        self.assertTrue(decision.eligible)

    def test_cfbe_mapping_requires_observed_model_identity(self):
        observation = CopilotRunObservation(
            task_id="FCX-COPILOT-TASK-001",
            role=CopilotRole.REVIEWER,
            observed_model="Gemini 3.1 Pro",
            credits_used=8.5,
            proof_ref="PR-123-REVIEW-RECEIPT",
            reality_state="C2",
            required_reality_state="C1",
            readiness="READY",
            quality=0.8,
            reliability=0.9,
            freshness=0.9,
            proof_strength=0.8,
            latency_penalty=0.2,
            cost_penalty=0.1,
            owner_burden_penalty=0.2,
            risk_penalty=0.2,
            model_identity_verified=False,
        )
        with self.assertRaises(ValueError):
            to_cfbe_route(observation)

    def test_cfbe_mapping_reuses_existing_capability_selector_contract(self):
        observation = CopilotRunObservation(
            task_id="FCX-COPILOT-TASK-001",
            role=CopilotRole.REVIEWER,
            observed_model="Gemini 3.1 Pro",
            credits_used=8.5,
            proof_ref="PR-123-REVIEW-RECEIPT",
            reality_state="C2",
            required_reality_state="C1",
            readiness="READY",
            quality=0.8,
            reliability=0.9,
            freshness=0.9,
            proof_strength=0.8,
            latency_penalty=0.2,
            cost_penalty=0.1,
            owner_burden_penalty=0.2,
            risk_penalty=0.2,
            model_identity_verified=True,
        )
        route = to_cfbe_route(observation)
        self.assertEqual(route.capability_id, "FCX-COPILOT-REVIEWER")
        self.assertEqual(route.authority_required, "A1_INTERNAL")
        self.assertFalse(route.external_effect)
        self.assertGreater(route.score, 0)

    def test_usage_receipt_never_claims_external_or_provider_effect(self):
        spec = self.task(role=CopilotRole.GEMINI_CHALLENGER, requested_model="Gemini 3.1 Pro")
        envelope = compile_task_envelope(spec)
        observation = CopilotRunObservation(
            task_id=spec.task_id,
            role=spec.role,
            observed_model="Gemini 3.1 Pro",
            credits_used=7,
            proof_ref="COPILOT-USAGE-READBACK-001",
            reality_state="C2",
            required_reality_state="C1",
            readiness="READY",
            quality=0.7,
            reliability=0.8,
            freshness=0.9,
            proof_strength=0.8,
            latency_penalty=0.2,
            cost_penalty=0.1,
            owner_burden_penalty=0.2,
            risk_penalty=0.2,
            model_identity_verified=True,
        )
        receipt = usage_receipt(
            observation=observation,
            task_envelope=envelope,
            budget_cycle_id="2026-08",
        )
        self.assertFalse(receipt["external_effect_claimed"])
        self.assertFalse(receipt["provider_effect_claimed"])
        self.assertEqual(receipt["observed_model"], "Gemini 3.1 Pro")
        self.assertEqual(receipt["credits_used"], 7.0)


if __name__ == "__main__":
    unittest.main()
