from __future__ import annotations

import os
import tempfile
import unittest

from .conversation_exhaustion import (
    ConversationExhaustionGuard,
    ConversationRiskState,
    ConversationSignals,
)
from .models import GovernanceCapsule
from .runtime import ChatBridgeOmega4
from .store import ChatBridgeStore


class ConversationExhaustionGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = ChatBridgeOmega4(
            ChatBridgeStore(os.path.join(self.tmp.name, "chatbridge.sqlite3"))
        )
        self.capsule = GovernanceCapsule(
            owner="Kim Kagiso Mosiane",
            project="Medical Accommodation",
            workstream="medical-accommodation",
            adapter="medical-accommodation",
            objective="Continue the medical-accommodation evidence workstream.",
            exact_next_action="Process the next verified evidence delta.",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_terminal_warning_forbids_false_same_chat_checkpoint_claim(self) -> None:
        result = ConversationExhaustionGuard.assess(
            ConversationSignals(
                conversation_key="chat-terminal",
                max_length_warning_observed=True,
                material_deltas_uncheckpointed=3,
            )
        )
        self.assertEqual(result["risk_state"], ConversationRiskState.TERMINAL.value)
        self.assertFalse(result["checkpoint_attempt_allowed"])
        self.assertFalse(result["same_chat_recovery_claim_allowed"])
        self.assertEqual(result["recovery_source"], "LAST_VERIFIED_CHECKPOINT")
        self.assertFalse(result["score_is_exact_provider_quota"])

    def test_material_delta_requires_checkpoint_even_when_risk_is_green(self) -> None:
        result = ConversationExhaustionGuard.assess(
            ConversationSignals(
                conversation_key="chat-green-delta",
                material_deltas_uncheckpointed=1,
            )
        )
        self.assertEqual(result["risk_state"], ConversationRiskState.GREEN.value)
        self.assertTrue(result["checkpoint_required"])
        self.assertTrue(result["checkpoint_reason"]["material_delta"])

    def test_heavy_operation_requires_write_ahead_checkpoint(self) -> None:
        result = ConversationExhaustionGuard.assess(
            ConversationSignals(
                conversation_key="chat-heavy",
                heavy_operation_pending=True,
            )
        )
        self.assertTrue(result["checkpoint_required"])
        self.assertTrue(result["checkpoint_reason"]["pre_heavy_operation"])
        self.assertFalse(result["new_heavy_work_allowed"])

    def test_high_observable_risk_requires_preemptive_migration(self) -> None:
        result = ConversationExhaustionGuard.assess(
            ConversationSignals(
                conversation_key="chat-red",
                substantive_turns=150,
                turns_since_checkpoint=10,
                estimated_context_chars=450000,
                recent_tool_output_tokens=6000,
                recent_large_outputs=3,
                material_deltas_uncheckpointed=2,
                heavy_operation_pending=True,
            )
        )
        self.assertEqual(result["risk_state"], ConversationRiskState.RED.value)
        self.assertTrue(result["checkpoint_required"])
        self.assertTrue(result["migration_required"])
        self.assertFalse(result["score_is_exact_provider_quota"])

    def test_runtime_guard_writes_and_restores_health_checkpoint(self) -> None:
        guarded = self.runtime.guard_turn(
            "medical-accommodation",
            self.capsule,
            signals=ConversationSignals(
                conversation_key="chat-medical",
                material_deltas_uncheckpointed=1,
                heavy_operation_pending=True,
            ),
            hot_state={"current_objective": "recover January review record"},
            warm_pointers=["drive:medical-matrix"],
        )
        self.assertEqual(guarded["state"], "WRITE_AHEAD_CHECKPOINT_VERIFIED")
        self.assertIsNotNone(guarded["checkpoint"])
        self.assertTrue(guarded["heavy_operation_release"])
        restored = self.runtime.restore(
            "medical-accommodation",
            destination_session_key="dest-medical",
        )
        self.assertEqual(
            restored["conversation_health_checkpoint"]["conversation_key"],
            "chat-medical",
        )
        self.assertEqual(
            restored["hot_state"]["current_objective"],
            "recover January review record",
        )
        self.assertTrue(restored["conversation_exhaustion_guard_required"])
        self.assertEqual(
            restored["conversation_exhaustion_contract"]["terminal_rule"],
            "RESTORE_FROM_LAST_VERIFIED_CHECKPOINT",
        )

    def test_terminal_guard_uses_last_checkpoint_without_new_generation(self) -> None:
        self.runtime.backup(
            "medical-accommodation",
            self.capsule,
            hot_state={"state": "SAFE_CHECKPOINT"},
        )
        before = len(self.runtime.history("medical-accommodation"))
        guarded = self.runtime.guard_turn(
            "medical-accommodation",
            self.capsule,
            signals=ConversationSignals(
                conversation_key="chat-terminal-medical",
                max_length_warning_observed=True,
            ),
            hot_state={"state": "UNSAFE_UNWRITTEN_TAIL"},
        )
        after = len(self.runtime.history("medical-accommodation"))
        self.assertEqual(before, after)
        self.assertFalse(guarded["same_chat_checkpoint_attempted"])
        self.assertEqual(
            guarded["state"],
            "TERMINAL_RESTORE_FROM_LAST_VERIFIED_CHECKPOINT",
        )
        self.assertEqual(
            guarded["last_verified_checkpoint"]["checkpoint_fingerprint"],
            self.runtime.status("medical-accommodation")["checkpoint_fingerprint"],
        )


if __name__ == "__main__":
    unittest.main()
