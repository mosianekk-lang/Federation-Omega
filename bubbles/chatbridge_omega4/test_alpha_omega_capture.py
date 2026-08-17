from __future__ import annotations

import os
import tempfile
import unittest

from .alpha_omega_capture import (
    AlphaOmegaConversationCapture,
    AlphaOmegaRestoreMode,
    CaptureObservation,
    CapturePath,
    CapturePathKind,
    CapturePathState,
    ConversationStream,
    ObservationConflict,
    StreamExpectation,
)
from .full_fidelity_ledger import (
    ConversationEventType,
    ConversationRole,
    EventExecutionState,
    FullFidelityConversationLedger,
    IncompleteTranscript,
)


class AlphaOmegaConversationCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "chatbridge.sqlite3")
        self.ledger = FullFidelityConversationLedger(self.db)
        self.engine = AlphaOmegaConversationCapture(self.db, self.ledger)
        self.key = "6a7decb0-1c5c-83ea-a85b-a915c10d47e0"
        self.namespace = "truthgrid-federation-canonicalisation"
        self.provider = CapturePath(
            conversation_key=self.key,
            path_id="provider-export",
            kind=CapturePathKind.NATIVE_EXPORT,
            source_provider="CHATGPT_EXPORT",
            proof_strength=1.0,
            completeness=1.0,
            freshness=1.0,
            independent_group="provider-native",
            authoritative=True,
        )
        self.dom = CapturePath(
            conversation_key=self.key,
            path_id="rendered-dom",
            kind=CapturePathKind.RENDERED_DOM,
            source_provider="CHATGPT_WEB",
            proof_strength=0.9,
            completeness=0.95,
            freshness=1.0,
            independent_group="browser-render",
        )
        self.engine.register_path(self.provider)
        self.engine.register_path(self.dom)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def observation(
        self,
        *,
        path_id: str,
        global_sequence: int | None,
        stream_sequence: int,
        stream: ConversationStream,
        role: ConversationRole,
        content,
        source_id: str,
        event_type: ConversationEventType = ConversationEventType.MESSAGE,
        execution_state: EventExecutionState = EventExecutionState.OBSERVED,
    ) -> CaptureObservation:
        return CaptureObservation(
            conversation_key=self.key,
            namespace_key=self.namespace,
            path_id=path_id,
            stream=stream,
            role=role,
            event_type=event_type,
            content=content,
            occurred_at=f"2026-08-17T01:00:{stream_sequence:02d}+02:00",
            global_sequence=global_sequence,
            stream_sequence=stream_sequence,
            source_event_id=source_id,
            source_turn_id=source_id,
            provider_event_id=source_id,
            idempotency_key=f"{path_id}:{source_id}",
            execution_state=execution_state,
        )

    def test_exact_multipath_multistream_restore(self) -> None:
        observations = []
        for path_id in (self.provider.path_id, self.dom.path_id):
            observations.extend(
                [
                    self.observation(
                        path_id=path_id,
                        global_sequence=1,
                        stream_sequence=1,
                        stream=ConversationStream.USER,
                        role=ConversationRole.USER,
                        content="start",
                        source_id="evt-1",
                    ),
                    self.observation(
                        path_id=path_id,
                        global_sequence=2,
                        stream_sequence=1,
                        stream=ConversationStream.ASSISTANT,
                        role=ConversationRole.ASSISTANT,
                        content="finish",
                        source_id="evt-2",
                    ),
                ]
            )
        captured = self.engine.capture(observations)
        self.assertEqual(captured["state"], "CAPTURE_RECONCILED_VERIFIED")
        self.engine.declare_stream_expectations(
            self.key,
            [
                StreamExpectation(ConversationStream.USER, 1, 1),
                StreamExpectation(ConversationStream.ASSISTANT, 1, 1),
            ],
        )
        finalized = self.engine.finalize(
            self.key,
            self.namespace,
            expected_last_sequence=2,
        )
        assessment = finalized["assessment"]
        self.assertTrue(assessment["exact_alpha_omega_complete"])
        self.assertEqual(
            assessment["restore_mode"],
            AlphaOmegaRestoreMode.EXACT_MULTIPATH_MULTISTREAM_RESTORE.value,
        )
        restored = self.engine.reconstruct(
            self.key,
            require_alpha_omega_exact=True,
        )
        self.assertEqual(
            [event["content"] for event in restored["transcript"]],
            ["start", "finish"],
        )
        self.assertEqual(
            restored["alpha_omega_assessment"]["minimum_independent_groups_per_event"],
            2,
        )

    def test_out_of_order_path_is_buffered_until_gap_arrives(self) -> None:
        second = self.observation(
            path_id=self.provider.path_id,
            global_sequence=2,
            stream_sequence=1,
            stream=ConversationStream.ASSISTANT,
            role=ConversationRole.ASSISTANT,
            content="second",
            source_id="evt-2",
        )
        first_result = self.engine.capture([second])
        self.assertEqual(
            first_result["reconciliation"]["pending_explicit_sequences"],
            [2],
        )
        first = self.observation(
            path_id=self.provider.path_id,
            global_sequence=1,
            stream_sequence=1,
            stream=ConversationStream.USER,
            role=ConversationRole.USER,
            content="first",
            source_id="evt-1",
        )
        second_result = self.engine.capture([first])
        self.assertEqual(
            second_result["reconciliation"]["ledger_after"]["event_count"],
            2,
        )
        reconstructed = self.ledger.reconstruct(self.key)
        self.assertEqual(
            [event["content"] for event in reconstructed["transcript"]],
            ["first", "second"],
        )

    def test_conflicting_paths_fail_closed(self) -> None:
        first = self.observation(
            path_id=self.provider.path_id,
            global_sequence=1,
            stream_sequence=1,
            stream=ConversationStream.USER,
            role=ConversationRole.USER,
            content="one version",
            source_id="evt-1",
        )
        self.engine.capture([first])
        conflicting = self.observation(
            path_id=self.dom.path_id,
            global_sequence=1,
            stream_sequence=1,
            stream=ConversationStream.USER,
            role=ConversationRole.USER,
            content="different version",
            source_id="evt-1",
        )
        result = self.engine.capture([conflicting])
        self.assertEqual(result["state"], "CAPTURE_CONFLICTED")
        assessment = self.engine.assess(self.key)
        self.assertEqual(
            assessment["restore_mode"],
            AlphaOmegaRestoreMode.REJECT_CONFLICTED.value,
        )
        with self.assertRaises(ObservationConflict):
            self.engine.reconstruct(self.key)

    def test_path_failure_reroutes_to_secondary_without_false_multipath_claim(self) -> None:
        self.engine.set_path_state(
            self.key,
            self.provider.path_id,
            CapturePathState.FAILED,
            reason="provider export unavailable",
        )
        observation = self.observation(
            path_id=self.dom.path_id,
            global_sequence=1,
            stream_sequence=1,
            stream=ConversationStream.USER,
            role=ConversationRole.USER,
            content="captured through secondary path",
            source_id="evt-1",
        )
        self.engine.capture([observation])
        self.engine.declare_stream_expectations(
            self.key,
            [StreamExpectation(ConversationStream.USER, 1, 1)],
        )
        finalized = self.engine.finalize(
            self.key,
            self.namespace,
            expected_last_sequence=1,
        )
        self.assertFalse(finalized["assessment"]["exact_alpha_omega_complete"])
        self.assertEqual(
            finalized["assessment"]["restore_mode"],
            AlphaOmegaRestoreMode.EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE.value,
        )
        self.assertEqual(
            finalized["assessment"]["ranked_failover_plan"][0]["path_id"],
            self.dom.path_id,
        )

    def test_derived_ordering_blocks_alpha_omega_exact_promotion(self) -> None:
        observation = self.observation(
            path_id=self.provider.path_id,
            global_sequence=None,
            stream_sequence=1,
            stream=ConversationStream.USER,
            role=ConversationRole.USER,
            content="timestamp ordered",
            source_id="evt-1",
        )
        self.engine.capture([observation])
        self.engine.declare_stream_expectations(
            self.key,
            [StreamExpectation(ConversationStream.USER, 1, 1)],
        )
        finalized = self.engine.finalize(
            self.key,
            self.namespace,
            expected_last_sequence=1,
        )
        self.assertEqual(finalized["assessment"]["derived_ordering_count"], 1)
        with self.assertRaises(IncompleteTranscript):
            self.engine.reconstruct(
                self.key,
                require_alpha_omega_exact=True,
            )

    def test_replay_chunks_stay_bounded_and_preserve_oversized_content(self) -> None:
        transcript = [
            {
                "sequence": 1,
                "role": "USER",
                "content": "x" * 20000,
                "event_hash": "a" * 64,
            },
            {
                "sequence": 2,
                "role": "ASSISTANT",
                "content": "done",
                "event_hash": "b" * 64,
            },
        ]
        chunks = self.engine.build_replay_chunks(transcript, token_limit=1000)
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(chunk["estimated_tokens"] <= 1000 for chunk in chunks))
        fragments = [
            item
            for chunk in chunks
            for item in chunk["payload"]
            if item.get("sequence") == 1
        ]
        self.assertGreater(len(fragments), 1)
        self.assertEqual(
            len({item["original_content_sha256"] for item in fragments}),
            1,
        )


if __name__ == "__main__":
    unittest.main()
