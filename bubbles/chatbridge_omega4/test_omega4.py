from __future__ import annotations

import os
import tempfile
import unittest

from .models import (
    ApprovalState,
    ContinuationMode,
    GovernanceCapsule,
    ProviderContinuationRef,
    RestorePreviewReason,
)
from .runtime import ChatBridgeOmega4
from .store import ChatBridgeStore, NamespaceCollision


class ChatBridgeOmega4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "chatbridge.sqlite3")
        self.runtime = ChatBridgeOmega4(ChatBridgeStore(self.db))
        self.capsule = GovernanceCapsule(
            owner="Kim Kagiso Mosiane",
            project="TUT 21 August Disciplinary",
            workstream="postponement",
            adapter="tut-21-august-disciplinary",
            objective="Preserve and resume the governed postponement workstream.",
            exact_next_action="Show the refined postponement draft on screen.",
            approval_gates=(ApprovalState.SCREEN_FIRST,),
            connector_permissions=("Gmail", "Google Drive"),
            active_specialists=("ChatGov", "Lex Advocate"),
            external_effects_allowed=False,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def backup(self, hot=None, namespace="TUT hearing"):
        return self.runtime.backup(
            namespace,
            self.capsule,
            hot_state=hot or {"draft_state": "UNSENT"},
            warm_pointers=["drive:heartbeat", "gmail:disciplinary-thread"],
            cold_pointers=["archive:historic-chat"],
        )

    def test_dynamic_namespace_backup_and_exact_restore(self) -> None:
        backup = self.backup()
        restored = self.runtime.restore("tut HEARING", destination_session_key="dest-1")
        self.assertEqual(restored["generation_id"], backup["generation_id"])
        self.assertEqual(restored["hot_state"]["draft_state"], "UNSENT")
        self.assertTrue(restored["consequential_action_locked"])
        self.assertIn("SCREEN_FIRST", restored["governance"]["approval_gates"])

    def test_same_material_checkpoint_is_idempotent(self) -> None:
        first = self.backup()
        second = self.backup()
        self.assertEqual(first["generation_id"], second["generation_id"])
        self.assertTrue(second["reused"])
        self.assertEqual(len(self.runtime.history("TUT hearing")), 1)

    def test_material_change_creates_new_generation(self) -> None:
        first = self.backup({"draft_state": "UNSENT"})
        second = self.backup({"draft_state": "APPROVED_NOT_SENT"})
        self.assertNotEqual(first["generation_id"], second["generation_id"])
        self.assertEqual(second["generation_number"], 2)
        self.assertEqual(len(self.runtime.history("TUT hearing")), 2)

    def test_namespace_collision_fails_closed(self) -> None:
        self.backup()
        other = GovernanceCapsule(
            owner="Kim Kagiso Mosiane",
            project="Kim Business Ideas",
            workstream="business-idea-3",
            adapter="business-ideas",
            objective="Trading business",
            exact_next_action="Continue research.",
        )
        with self.assertRaises(NamespaceCollision):
            self.runtime.backup("TUT hearing", other, hot_state={})

    def test_clone_creates_independent_branch(self) -> None:
        self.backup()
        branch = self.runtime.clone("TUT hearing", "TUT hearing strategy B")
        self.assertEqual(branch["state"], "BRANCH_CREATED_VERIFIED_LOCAL")
        branch_restore = self.runtime.restore(
            "TUT hearing strategy B", destination_session_key="dest-branch"
        )
        self.assertTrue(branch_restore["preview_required"])
        self.assertIn(
            RestorePreviewReason.BRANCHED_NAMESPACE.value,
            branch_restore["preview_reasons"],
        )
        self.assertNotEqual(
            self.runtime.status("TUT hearing")["namespace_id"],
            self.runtime.status("TUT hearing strategy B")["namespace_id"],
        )

    def test_rename_preserves_namespace_identity_and_history(self) -> None:
        self.backup()
        before = self.runtime.status("TUT hearing")
        renamed = self.runtime.rename("TUT hearing", "TUT disciplinary")
        self.assertEqual(before["namespace_id"], renamed["namespace_id"])
        history = self.runtime.history("TUT disciplinary")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["namespace_display_snapshot"], "TUT hearing")

    def test_release_tombstones_and_requires_preview(self) -> None:
        self.backup()
        released = self.runtime.release("TUT hearing")
        self.assertEqual(released["lifecycle_state"], "RELEASED")
        self.assertEqual(released["tombstone_state"], "TOMBSTONED")
        restored = self.runtime.restore("TUT hearing", destination_session_key="dest-release")
        self.assertEqual(restored["restore_state"], "RESTORE_PREVIEW_REQUIRED")
        self.assertIn(
            RestorePreviewReason.RELEASED_NAMESPACE.value,
            restored["preview_reasons"],
        )

    def test_historical_generation_restore_does_not_rebind_active_pointer(self) -> None:
        self.backup({"draft_state": "v1"})
        latest = self.backup({"draft_state": "v2"})
        historical = self.runtime.restore(
            "TUT hearing", destination_session_key="dest-history", generation_number=1
        )
        self.assertEqual(historical["restore_state"], "RESTORE_PREVIEW_REQUIRED")
        self.assertIn(
            RestorePreviewReason.HISTORICAL_GENERATION.value,
            historical["preview_reasons"],
        )
        self.assertEqual(
            self.runtime.status("TUT hearing")["active_generation_id"],
            latest["generation_id"],
        )

    def test_restore_lease_reuses_same_destination_generation(self) -> None:
        self.backup()
        first = self.runtime.restore("TUT hearing", destination_session_key="dest-lease")
        second = self.runtime.restore("TUT hearing", destination_session_key="dest-lease")
        self.assertEqual(first["lease_id"], second["lease_id"])
        self.assertTrue(second["lease_reused"])

    def test_provider_continuation_strategies_are_mutually_exclusive(self) -> None:
        valid = ProviderContinuationRef(
            mode=ContinuationMode.OPENAI_CONVERSATION,
            provider="openai",
            conversation_id="conv_123",
        )
        self.assertEqual(valid.conversation_id, "conv_123")
        with self.assertRaises(ValueError):
            ProviderContinuationRef(
                mode=ContinuationMode.OPENAI_CONVERSATION,
                provider="openai",
                conversation_id="conv_123",
                previous_response_id="resp_123",
            )


if __name__ == "__main__":
    unittest.main()
