from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from .full_fidelity_ledger import (
    ArtifactAvailability,
    ArtifactReference,
    ConversationEvent,
    ConversationEventType,
    ConversationRole,
    EventExecutionState,
    FullFidelityConversationLedger,
    IncompleteTranscript,
    PayloadAvailability,
    TranscriptConflict,
    TranscriptIntegrityError,
)


class FullFidelityConversationLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "chatbridge.sqlite3")
        self.ledger = FullFidelityConversationLedger(self.path)
        self.key = "conversation-exact-001"
        self.ledger.bind(
            self.key,
            "truthgrid-federation-canonicalisation",
            title="TruthGrid exact source",
        )

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
        payload_availability: PayloadAvailability = PayloadAvailability.RAW_GOVERNED,
        artifacts=(),
    ) -> ConversationEvent:
        return ConversationEvent(
            conversation_key=self.key,
            sequence=sequence,
            role=role,
            event_type=event_type,
            content=content,
            occurred_at=f"2026-08-17T00:00:0{sequence}+02:00",
            source_turn_id=f"turn-{sequence}",
            idempotency_key=f"idem-{sequence}",
            execution_state=execution_state,
            payload_availability=payload_availability,
            artifacts=tuple(artifacts),
        )

    def test_exact_start_to_finish_reconstruction(self) -> None:
        self.ledger.append_many(
            [
                self._event(1, ConversationRole.USER, "start"),
                self._event(2, ConversationRole.ASSISTANT, "analysis"),
                self._event(
                    3,
                    ConversationRole.TOOL,
                    {"state": "verified"},
                    event_type=ConversationEventType.TOOL_RESULT,
                    execution_state=EventExecutionState.EXECUTED_VERIFIED,
                ),
            ]
        )
        sealed = self.ledger.seal(
            self.key,
            expected_last_sequence=3,
            closure_reason="PREEMPTIVE_MIGRATION",
        )
        self.assertTrue(sealed["exact_context_complete"])
        self.assertEqual(sealed["integrity_state"], "PASS_EXACT")
        restored = self.ledger.reconstruct(self.key, require_exact=True)
        self.assertEqual(restored["restore_mode"], "EXACT_TRANSCRIPT_RESTORE")
        self.assertEqual(
            [item["content"] for item in restored["transcript"]],
            ["start", "analysis", {"state": "verified"}],
        )
        self.assertRegex(restored["context_manifest"]["merkle_root"], r"^[0-9a-f]{64}$")

    def test_gap_is_bounded_and_never_guessed(self) -> None:
        self.ledger.append(self._event(1, ConversationRole.USER, "first"))
        self.ledger.append(
            self._event(3, ConversationRole.ASSISTANT, "third"),
            allow_gap=True,
        )
        sealed = self.ledger.seal(self.key, expected_last_sequence=3)
        self.assertFalse(sealed["exact_context_complete"])
        self.assertEqual(sealed["missing_ranges"], [{"start": 2, "end": 2}])
        restored = self.ledger.reconstruct(self.key)
        self.assertEqual(restored["restore_mode"], "BOUNDED_TRANSCRIPT_RESTORE")
        self.assertEqual(len(restored["transcript"]), 2)
        with self.assertRaises(IncompleteTranscript):
            self.ledger.reconstruct(self.key, require_exact=True)

    def test_duplicate_is_idempotent_but_conflict_fails(self) -> None:
        event = self._event(1, ConversationRole.USER, "same")
        first = self.ledger.append(event)
        second = self.ledger.append(event)
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        with self.assertRaises(TranscriptConflict):
            self.ledger.append(self._event(1, ConversationRole.USER, "different"))

    def test_tamper_breaks_hash_chain(self) -> None:
        self.ledger.append(self._event(1, ConversationRole.USER, "original"))
        self.ledger.seal(self.key, expected_last_sequence=1)
        conn = sqlite3.connect(self.path)
        conn.execute(
            """
            UPDATE conversation_events
            SET content_json=?
            WHERE conversation_key=? AND sequence=1
            """,
            ('"tampered"', self.key),
        )
        conn.commit()
        conn.close()
        verification = self.ledger.verify(self.key)
        self.assertEqual(verification["integrity_state"], "FAIL_HASH_CHAIN")
        with self.assertRaises(TranscriptIntegrityError):
            self.ledger.reconstruct(self.key)

    def test_unavailable_attachment_downgrades_exact_restore(self) -> None:
        artifact = ArtifactReference(
            artifact_key="attachment-1",
            filename="evidence.pdf",
            sha256="a" * 64,
            locator="drive:attachment-1",
            availability=ArtifactAvailability.MISSING,
        )
        self.ledger.append(
            self._event(
                1,
                ConversationRole.USER,
                "attached",
                artifacts=(artifact,),
            )
        )
        verification = self.ledger.seal(self.key, expected_last_sequence=1)
        self.assertFalse(verification["exact_context_complete"])
        self.assertEqual(
            verification["unresolved_artifacts"][0]["artifact_key"],
            "attachment-1",
        )

    def test_redacted_payload_cannot_be_exact(self) -> None:
        self.ledger.append(
            self._event(
                1,
                ConversationRole.USER,
                "[redacted]",
                payload_availability=PayloadAvailability.REDACTED,
            )
        )
        verification = self.ledger.seal(self.key, expected_last_sequence=1)
        self.assertFalse(verification["exact_context_complete"])
        self.assertEqual(verification["unavailable_sequences"], [1])


if __name__ == "__main__":
    unittest.main()
