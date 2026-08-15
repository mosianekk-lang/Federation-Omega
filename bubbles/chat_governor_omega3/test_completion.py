from __future__ import annotations

import os
import tempfile
import unittest

from bubbles.chatbridge_omega4.completion_witness import (
    CompletionObservation,
    ContinuationClass,
    PendingUserTask,
    TaskCompletionState,
    WitnessMode,
)

from .completion import ChatGovCompletionInterlock
from .state import DurableState


class ChatGovCompletionInterlockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state = DurableState(os.path.join(self.tmp.name, "governor.sqlite3"))
        self.interlock = ChatGovCompletionInterlock(self.state)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _task(self, continuation=ContinuationClass.SAFE_INTERNAL) -> PendingUserTask:
        return PendingUserTask(
            task_id="task-key",
            task_type="SECURE_UI_ACTION",
            expected_effect="Create a key.",
            continuation_action="Prepare provider canary.",
            witness_modes=(WitnessMode.PROVIDER_READBACK, WitnessMode.USER_ASSERTION),
            continuation_class=continuation,
            provider="openai",
        )

    def test_provider_verified_completion_is_proof_bearing_and_clears_blocker(self) -> None:
        result = self.interlock.reconcile(
            "mission-1",
            self._task(),
            (
                CompletionObservation(
                    witness_mode=WitnessMode.PROVIDER_READBACK,
                    success=True,
                    provider="openai",
                    evidence_ref="provider:readback:1",
                ),
            ),
            trigger="START_OF_TURN",
        )
        self.assertEqual(result.decision.state, TaskCompletionState.PROVIDER_VERIFIED_COMPLETED)
        self.assertTrue(result.stale_blocker_cleared)
        cp = self.state.latest_checkpoint("mission-1")
        self.assertEqual(cp["proof_bearing"], 1)

    def test_owner_assertion_allows_safe_resume_but_is_not_provider_proof(self) -> None:
        result = self.interlock.reconcile(
            "mission-2",
            self._task(),
            (
                CompletionObservation(
                    witness_mode=WitnessMode.USER_ASSERTION,
                    success=True,
                    provider="openai",
                    evidence_ref="chat:done",
                ),
            ),
            trigger="PRE_USER_PROMPT",
        )
        self.assertEqual(result.decision.state, TaskCompletionState.OWNER_ASSERTED_COMPLETED)
        self.assertTrue(result.auto_resume_safe)
        self.assertFalse(result.decision.may_make_terminal_provider_claim)
        cp = self.state.latest_checkpoint("mission-2")
        self.assertEqual(cp["proof_bearing"], 0)

    def test_consequential_action_remains_locked_on_owner_assertion(self) -> None:
        result = self.interlock.reconcile(
            "mission-3",
            self._task(ContinuationClass.CONSEQUENTIAL_EXTERNAL),
            (
                CompletionObservation(
                    witness_mode=WitnessMode.USER_ASSERTION,
                    success=True,
                    provider="openai",
                    evidence_ref="chat:done",
                ),
            ),
            trigger="PRE_USER_PROMPT",
        )
        self.assertFalse(result.stale_blocker_cleared)
        self.assertFalse(result.auto_resume_safe)

    def test_pre_user_prompt_auto_probe_prevents_redundant_user_question(self) -> None:
        def broken_probe():
            raise RuntimeError("unavailable")

        def owner_probe():
            return CompletionObservation(
                witness_mode=WitnessMode.USER_ASSERTION,
                success=True,
                provider="openai",
                evidence_ref="chat:already-done",
            )

        result = self.interlock.before_user_prompt(
            "mission-4", self._task(), (broken_probe, owner_probe)
        )
        self.assertTrue(result.stale_blocker_cleared)
        self.assertEqual(result.decision.state, TaskCompletionState.OWNER_ASSERTED_COMPLETED)


if __name__ == "__main__":
    unittest.main()
