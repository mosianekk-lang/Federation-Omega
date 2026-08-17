from __future__ import annotations

import os
import tempfile
import unittest

from .alpha_omega_capture import (
    AlphaOmegaRestoreMode,
    CaptureObservation,
    CapturePath,
    CapturePathKind,
    ConversationStream,
    StreamExpectation,
)
from .full_fidelity_ledger import (
    ConversationEventType,
    ConversationRole,
    EventExecutionState,
    IncompleteTranscript,
)
from .models import GovernanceCapsule
from .runtime_omega49 import ChatBridgeOmega49
from .store import ChatBridgeStore


class ChatBridgeOmega49RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = ChatBridgeOmega49(
            ChatBridgeStore(os.path.join(self.tmp.name, "chatbridge.sqlite3"))
        )
        self.key = "6a7decb0-1c5c-83ea-a85b-a915c10d47e0"
        self.namespace = "truthgrid-federation-canonicalisation"
        self.capsule = GovernanceCapsule(
            owner="Kim Kagiso Mosiane",
            project="TruthGrid",
            workstream=self.namespace,
            adapter="TRUTHGRID_FEDERATION_CANONICALISATION_LEX_FIRST",
            objective="Preserve complete start-to-finish context through Alpha→Omega paths and streams.",
            exact_next_action="Resume LEX-first component qualification.",
        )
        self.paths = (
            CapturePath(
                conversation_key=self.key,
                path_id="provider-export",
                kind=CapturePathKind.NATIVE_EXPORT,
                source_provider="CHATGPT_EXPORT",
                proof_strength=1.0,
                completeness=1.0,
                independent_group="provider-native",
                authoritative=True,
            ),
            CapturePath(
                conversation_key=self.key,
                path_id="browser-render",
                kind=CapturePathKind.RENDERED_DOM,
                source_provider="CHATGPT_WEB",
                proof_strength=0.9,
                completeness=1.0,
                independent_group="browser-render",
            ),
        )
        for path in self.paths:
            self.runtime.register_capture_path(path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def observation(self, path_id: str, sequence: int, content: str) -> CaptureObservation:
        stream = ConversationStream.USER if sequence == 1 else ConversationStream.ASSISTANT
        role = ConversationRole.USER if sequence == 1 else ConversationRole.ASSISTANT
        return CaptureObservation(
            conversation_key=self.key,
            namespace_key=self.namespace,
            path_id=path_id,
            stream=stream,
            role=role,
            event_type=ConversationEventType.MESSAGE,
            content=content,
            occurred_at=f"2026-08-17T01:00:0{sequence}+02:00",
            global_sequence=sequence,
            stream_sequence=1,
            source_event_id=f"evt-{sequence}",
            source_turn_id=f"turn-{sequence}",
            provider_event_id=f"evt-{sequence}",
            idempotency_key=f"{path_id}:evt-{sequence}",
            execution_state=EventExecutionState.OBSERVED,
        )

    def test_exact_alpha_omega_checkpoint_survives_backup_and_restore(self) -> None:
        observations = []
        for path in self.paths:
            observations.extend(
                [
                    self.observation(path.path_id, 1, "start"),
                    self.observation(path.path_id, 2, "finish"),
                ]
            )
        self.runtime.capture_multipath_stream_events(observations)
        self.runtime.declare_stream_expectations(
            self.key,
            [
                StreamExpectation(ConversationStream.USER, 1, 1),
                StreamExpectation(ConversationStream.ASSISTANT, 1, 1),
            ],
        )
        finalized = self.runtime.finalize_multipath_stream_capture(
            self.key,
            self.namespace,
            expected_last_sequence=2,
        )
        self.assertTrue(finalized["assessment"]["exact_alpha_omega_complete"])

        backup = self.runtime.backup(
            self.namespace,
            self.capsule,
            hot_state={"next_action": "LEX qualification"},
            conversation_ledger_key=self.key,
        )
        self.assertEqual(backup["chatbridge_version"], ChatBridgeOmega49.VERSION)
        self.assertEqual(
            backup["alpha_omega_capture_checkpoint"]["restore_mode"],
            AlphaOmegaRestoreMode.EXACT_MULTIPATH_MULTISTREAM_RESTORE.value,
        )

        restored = self.runtime.restore(
            self.namespace,
            destination_session_key="successor-chat",
            require_alpha_omega_exact=True,
        )
        alpha_restore = restored["alpha_omega_conversation_restore"]
        self.assertTrue(alpha_restore["exact_alpha_omega_complete"])
        self.assertEqual(
            [event["content"] for event in alpha_restore["transcript"]],
            ["start", "finish"],
        )
        self.assertGreaterEqual(len(alpha_restore["replay_chunks"]), 1)
        self.assertNotIn(
            self.runtime.ALPHA_OMEGA_CAPTURE_KEY,
            restored["hot_state"],
        )
        self.assertTrue(
            restored["restore_directives"]["alpha_omega_multipath_multistream"]
        )

    def test_legacy_checkpoint_is_not_overcertified(self) -> None:
        self.runtime.backup(
            "legacy",
            self.capsule,
            hot_state={"state": "legacy"},
        )
        restored = self.runtime.restore(
            "legacy",
            destination_session_key="legacy-successor",
        )
        self.assertEqual(
            restored["alpha_omega_conversation_restore"]["restore_mode"],
            "LEGACY_NO_ALPHA_OMEGA_CAPTURE_CHECKPOINT",
        )
        with self.assertRaises(IncompleteTranscript):
            self.runtime.restore(
                "legacy",
                destination_session_key="legacy-exact",
                require_alpha_omega_exact=True,
            )


if __name__ == "__main__":
    unittest.main()
