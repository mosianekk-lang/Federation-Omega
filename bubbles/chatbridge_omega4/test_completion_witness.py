from __future__ import annotations

import unittest

from .completion_witness import (
    CompletionObservation,
    CompletionWitnessEngine,
    ContinuationClass,
    PendingUserTask,
    TaskCompletionState,
    WitnessMode,
)


class CompletionWitnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CompletionWitnessEngine()
        self.key_task = PendingUserTask(
            task_id="task-openai-key",
            task_type="SECURE_UI_ACTION",
            expected_effect="Create the ChatBridge Omega4 Provider Canary API key.",
            continuation_action="Continue source/runtime preparation and attempt provider readback.",
            witness_modes=(
                WitnessMode.PROVIDER_READBACK,
                WitnessMode.APP_CALLBACK,
                WitnessMode.USER_ASSERTION,
                WitnessMode.UI_OPAQUE,
            ),
            continuation_class=ContinuationClass.SAFE_INTERNAL,
            correlation_ref="ChatBridge Omega4 Provider Canary",
            provider="openai",
            allow_owner_assertion_for_safe_continuation=True,
            require_provider_verification_for_terminal_claim=True,
        )

    def test_provider_readback_verifies_and_continues(self) -> None:
        decision = self.engine.reconcile(
            self.key_task,
            (
                CompletionObservation(
                    witness_mode=WitnessMode.PROVIDER_READBACK,
                    success=True,
                    correlation_ref="ChatBridge Omega4 Provider Canary",
                    provider="openai",
                    evidence_ref="provider:key-readback:123",
                ),
            ),
        )
        self.assertEqual(decision.state, TaskCompletionState.PROVIDER_VERIFIED_COMPLETED)
        self.assertTrue(decision.may_continue)
        self.assertTrue(decision.may_make_terminal_provider_claim)

    def test_owner_done_allows_safe_work_but_not_provider_claim(self) -> None:
        decision = self.engine.reconcile(
            self.key_task,
            (
                CompletionObservation(
                    witness_mode=WitnessMode.USER_ASSERTION,
                    success=True,
                    correlation_ref="ChatBridge Omega4 Provider Canary",
                    provider="openai",
                    evidence_ref="chat:user-said-done",
                ),
            ),
        )
        self.assertEqual(decision.state, TaskCompletionState.OWNER_ASSERTED_COMPLETED)
        self.assertTrue(decision.may_continue)
        self.assertFalse(decision.may_make_terminal_provider_claim)

    def test_opaque_ui_event_does_not_become_verified_completion(self) -> None:
        decision = self.engine.reconcile(
            self.key_task,
            (
                CompletionObservation(
                    witness_mode=WitnessMode.UI_OPAQUE,
                    success=True,
                    correlation_ref="ChatBridge Omega4 Provider Canary",
                    provider="openai",
                    evidence_ref="opaque-ui-click",
                ),
            ),
        )
        self.assertEqual(decision.state, TaskCompletionState.PENDING)
        self.assertFalse(decision.may_continue)
        self.assertFalse(decision.may_make_terminal_provider_claim)

    def test_consequential_continuation_does_not_unlock_on_owner_assertion(self) -> None:
        task = PendingUserTask(
            task_id="task-send",
            task_type="CONSEQUENTIAL_ACTION",
            expected_effect="Send an external filing.",
            continuation_action="Send filing.",
            witness_modes=(WitnessMode.USER_ASSERTION, WitnessMode.PROVIDER_READBACK),
            continuation_class=ContinuationClass.CONSEQUENTIAL_EXTERNAL,
        )
        decision = self.engine.reconcile(
            task,
            (
                CompletionObservation(
                    witness_mode=WitnessMode.USER_ASSERTION,
                    success=True,
                    evidence_ref="chat:done",
                ),
            ),
        )
        self.assertEqual(decision.state, TaskCompletionState.OWNER_ASSERTED_COMPLETED)
        self.assertFalse(decision.may_continue)

    def test_auto_reconcile_ignores_failed_probe_and_uses_available_readback(self) -> None:
        def broken_probe():
            raise RuntimeError("connector unavailable")

        def readback_probe():
            return CompletionObservation(
                witness_mode=WitnessMode.PROVIDER_READBACK,
                success=True,
                correlation_ref="ChatBridge Omega4 Provider Canary",
                provider="openai",
                evidence_ref="provider:key-readback:456",
            )

        decision = self.engine.auto_reconcile(self.key_task, (broken_probe, readback_probe))
        self.assertEqual(decision.state, TaskCompletionState.PROVIDER_VERIFIED_COMPLETED)
        self.assertTrue(decision.may_continue)


if __name__ == "__main__":
    unittest.main()
