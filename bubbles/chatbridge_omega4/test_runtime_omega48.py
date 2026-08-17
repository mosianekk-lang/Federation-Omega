from __future__ import annotations

import os
import tempfile
import unittest

from .conversation_exhaustion import ConversationSignals
from .full_fidelity_ledger import (
    ConversationEvent,
    ConversationEventType,
    ConversationRole,
    EventExecutionState,
    IncompleteTranscript,
    TerminalExecutionClaimError,
)
from .models import GovernanceCapsule
from .runtime_omega48 import ChatBridgeOmega48
from .store import ChatBridgeStore


class ChatBridgeOmega48RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = ChatBridgeOmega48(
            ChatBridgeStore(os.path.join(self.tmp.name, "chatbridge.sqlite3"))
        )
        self.capsule = GovernanceCapsule(
            owner="Kim Kagiso Mosiane",
            project="TruthGrid",
            workstream="truthgrid-federation-canonicalisation",
            adapter="TRUTHGRID_FEDERATION_CANONICALISATION_LEX_FIRST",
            objective="Preserve the complete conversation context.",
            exact_next_action="Resume LEX-first component qualification.",
        )
        self.namespace = "truthgrid-federation-canonicalisation"
        self.conversation_key = "6a7decb0-1c5c-83ea-a85b-a915c10d47e0"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _event(
        self,
        sequence: int,
        role: ConversationRole,
        content,
        *,
        event_type: ConversationEventType = ConversationEventType.MESSAGE,
        execution_state: EventExecutionState = EventExecutionState.OBSERVED,
    ) -> ConversationEvent:
        return ConversationEvent(
            conversation_key=self.conversation_key,
            sequence=sequence,
            role=role,
            event_type=event_type,
            content=content,
            occurred_at=f"2026-08-17T01:00:0{sequence}+02:00",
            source_turn_id=f"turn-{sequence}",
            idempotency_key=f"turn-{sequence}",
            execution_state=execution_state,
        )

    def test_exact_transcript_is_bound_to_checkpoint_and_restored(self) -> None:
        self.runtime.capture_conversation_events(
            self.namespace,
            [
                self._event(1, ConversationRole.USER, "start"),
                self._event(2, ConversationRole.ASSISTANT, "middle"),
                self._event(3, ConversationRole.USER, "finish"),
            ],
            title="TruthGrid full conversation",
        )
        self.runtime.seal_conversation_ledger(
            self.conversation_key,
            expected_last_sequence=3,
            closure_reason="PREEMPTIVE_MIGRATION",
        )
        backup = self.runtime.backup(
            self.namespace,
            self.capsule,
            hot_state={"next_action": "LEX qualification"},
            conversation_ledger_key=self.conversation_key,
        )
        self.assertEqual(
            backup["chatbridge_version"],
            "CHATBRIDGE-Ω4.8-FULL-FIDELITY-CONVERSATION-LEDGER",
        )
        restored = self.runtime.restore(
            self.namespace,
            destination_session_key="destination-chat",
            require_exact_transcript=True,
        )
        self.assertEqual(
            restored["conversation_transcript_restore"]["restore_mode"],
            "EXACT_TRANSCRIPT_RESTORE",
        )
        self.assertEqual(
            [
                turn["content"]
                for turn in restored["conversation_transcript_restore"]["transcript"]
            ],
            ["start", "middle", "finish"],
        )
        self.assertNotIn(
            self.runtime.CONVERSATION_LEDGER_KEY,
            restored["hot_state"],
        )
        self.assertTrue(
            restored["restore_directives"]["capture_every_observed_turn"]
        )

    def test_legacy_checkpoint_is_explicitly_bounded(self) -> None:
        self.runtime.backup(
            "legacy",
            self.capsule,
            hot_state={"state": "legacy"},
        )
        restored = self.runtime.restore(
            "legacy",
            destination_session_key="legacy-destination",
        )
        self.assertEqual(
            restored["conversation_transcript_restore"]["restore_mode"],
            "LEGACY_CHECKPOINT_NO_TRANSCRIPT_LEDGER",
        )
        self.assertFalse(
            restored["conversation_transcript_restore"]["exact_context_complete"]
        )
        with self.assertRaises(IncompleteTranscript):
            self.runtime.restore(
                "legacy",
                destination_session_key="legacy-destination-exact",
                require_exact_transcript=True,
            )

    def test_terminal_execution_claim_is_rejected(self) -> None:
        event = self._event(
            1,
            ConversationRole.USER,
            "chatbridge - LEX",
            execution_state=EventExecutionState.EXECUTED_VERIFIED,
        )
        with self.assertRaises(TerminalExecutionClaimError):
            self.runtime.guard_turn(
                self.namespace,
                self.capsule,
                signals=ConversationSignals(
                    conversation_key=self.conversation_key,
                    max_length_warning_observed=True,
                ),
                hot_state={"state": "terminal"},
                conversation_event=event,
            )

    def test_terminal_attempt_is_captured_but_not_called_executed(self) -> None:
        event = self._event(
            1,
            ConversationRole.USER,
            "chatbridge - LEX",
            execution_state=EventExecutionState.NOT_EXECUTED_TERMINAL,
        )
        result = self.runtime.guard_turn(
            self.namespace,
            self.capsule,
            signals=ConversationSignals(
                conversation_key=self.conversation_key,
                max_length_warning_observed=True,
            ),
            hot_state={"state": "terminal"},
            conversation_event=event,
        )
        self.assertEqual(
            result["state"],
            "TERMINAL_RESTORE_FROM_LAST_VERIFIED_CHECKPOINT",
        )
        self.assertEqual(
            result["conversation_capture"]["state"],
            "EVENT_CAPTURED_VERIFIED",
        )
        self.assertEqual(
            result["conversation_terminal_seal"]["integrity_state"],
            "PASS_EXACT",
        )
        restored = self.runtime.reconstruct_conversation(
            self.conversation_key,
            require_exact=True,
        )
        self.assertEqual(
            restored["transcript"][0]["execution_state"],
            "NOT_EXECUTED_TERMINAL",
        )


if __name__ == "__main__":
    unittest.main()
