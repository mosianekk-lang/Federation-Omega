from __future__ import annotations

import unittest

from bubbles.chatbridge_omega4.completion_witness import (
    CompletionObservation,
    ContinuationClass,
    PendingUserTask,
    WitnessMode,
)
from evidenceops.caseforge.completion_witness_aaa_canary import (
    ClaimClass,
    CompletionWitnessHomeAdapter,
    HOME_POLICIES,
    run_default_completion_witness_aaa_canary,
)


class CompletionWitnessAAACanaryTests(unittest.TestCase):
    def _task(self, continuation=ContinuationClass.SAFE_INTERNAL) -> PendingUserTask:
        return PendingUserTask(
            task_id="task-1",
            task_type="AAA_SHADOW",
            expected_effect="Complete owner/provider dependency.",
            continuation_action="Resume safe work.",
            witness_modes=(WitnessMode.PROVIDER_READBACK, WitnessMode.USER_ASSERTION),
            continuation_class=continuation,
            provider="openai",
            require_provider_verification_for_terminal_claim=True,
        )

    @staticmethod
    def _owner() -> CompletionObservation:
        return CompletionObservation(
            witness_mode=WitnessMode.USER_ASSERTION,
            success=True,
            provider="openai",
            evidence_ref="owner:done",
        )

    @staticmethod
    def _provider() -> CompletionObservation:
        return CompletionObservation(
            witness_mode=WitnessMode.PROVIDER_READBACK,
            success=True,
            provider="openai",
            evidence_ref="provider:verified",
        )

    def test_provider_readback_remains_terminal_proof_in_every_home(self) -> None:
        for policy in HOME_POLICIES.values():
            result = CompletionWitnessHomeAdapter(policy).reconcile(
                self._task(),
                ClaimClass.PROVIDER_TERMINAL_STATE,
                (self._provider(),),
            )
            self.assertTrue(result["may_continue"], policy.system_id)
            self.assertTrue(result["may_make_terminal_provider_claim"], policy.system_id)

    def test_owner_assertion_releases_safe_internal_work_without_terminal_claim(self) -> None:
        for policy in HOME_POLICIES.values():
            result = CompletionWitnessHomeAdapter(policy).reconcile(
                self._task(),
                ClaimClass.SAFE_INTERNAL_CONTINUATION,
                (self._owner(),),
            )
            self.assertTrue(result["may_continue"], policy.system_id)
            self.assertFalse(result["may_make_terminal_provider_claim"], policy.system_id)

    def test_alpha2_claim_class_separation_blocks_evidentiary_promotion(self) -> None:
        for policy in HOME_POLICIES.values():
            result = CompletionWitnessHomeAdapter(policy).reconcile(
                self._task(),
                ClaimClass.EVIDENTIARY_FACT_PROMOTION,
                (self._owner(),),
            )
            self.assertFalse(result["may_continue"], policy.system_id)
            self.assertFalse(result["may_make_terminal_provider_claim"], policy.system_id)
            self.assertTrue(result["alpha2_scope_block"], policy.system_id)

    def test_consequential_external_action_remains_locked_on_owner_assertion(self) -> None:
        for policy in HOME_POLICIES.values():
            result = CompletionWitnessHomeAdapter(policy).reconcile(
                self._task(ContinuationClass.CONSEQUENTIAL_EXTERNAL),
                ClaimClass.CONSEQUENTIAL_EXTERNAL_ACTION,
                (self._owner(),),
            )
            self.assertFalse(result["may_continue"], policy.system_id)
            self.assertFalse(result["may_make_terminal_provider_claim"], policy.system_id)

    def test_default_canary_compounds_across_three_homes_without_material_regression(self) -> None:
        receipt = run_default_completion_witness_aaa_canary()
        self.assertEqual("GENE-COMPLETION-WITNESS-AAA-001", receipt.capability_id)
        self.assertEqual("CHATBRIDGE", receipt.source_system)
        self.assertEqual("SHADOW_VALIDATED", receipt.status)
        self.assertFalse(receipt.external_effect)
        self.assertEqual(
            "DETERMINISTIC_SYNTHETIC_WORKLOAD_ONLY_NOT_PROVIDER_RUNTIME",
            receipt.proof_scope,
        )
        self.assertEqual(
            {"CHATGOV", "EVIDENCEOPS", "TRUTHGRID"},
            set(receipt.candidate_homes),
        )
        self.assertEqual(receipt.candidate_homes, receipt.redistributed_to)
        self.assertEqual("CLAIM_CLASS_SEPARATION", receipt.feedback_improvement)

        for result in receipt.home_results:
            self.assertTrue(result.no_material_regression, result.system_id)
            self.assertGreater(result.intelligence_density.delta, 0.0, result.system_id)
            self.assertEqual(0, result.metrics.unsafe_continuations, result.system_id)
            self.assertEqual(0, result.metrics.false_terminal_provider_claims, result.system_id)
            self.assertEqual(0, result.metrics.blocked_safe_continuations, result.system_id)
            self.assertGreater(
                result.metrics.redundant_owner_prompts_baseline,
                result.metrics.redundant_owner_prompts_candidate,
                result.system_id,
            )
            self.assertGreater(result.metrics.alpha2_scope_blocks, 0, result.system_id)


if __name__ == "__main__":
    unittest.main()
