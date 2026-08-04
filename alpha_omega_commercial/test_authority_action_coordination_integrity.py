from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authority_action_coordination_integrity import (
    IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


class AuthorityActionCoordinationIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _quote_plane(self, quote_id: str = "QUOTE-INTEGRITY"):
        bootstrap = IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        lead_id = quote_id.replace("QUOTE", "LEAD")
        bootstrap.create_lead(lead_id, "org", "inbound", "manual delay")
        bootstrap.create_quote_draft(
            quote_id,
            lead_id,
            "AO-PILOT",
            "ZAR",
            560000.0,
            12,
        )
        subject = bootstrap.quote_authority_subject(quote_id)
        receipt = owner_receipt(
            "OWNER-" + quote_id,
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        return plane, receipt

    def test_successful_quote_uses_identity_pinned_canonical_class(self) -> None:
        plane, receipt = self._quote_plane()
        quote = plane.approve_quote(
            "QUOTE-INTEGRITY",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(
            quote["authority_action_commit"]["state"],
            "ATOMIC_AUTHORITY_ACTION_COMMITTED",
        )
        integrity = plane.authority_action_coordination_integrity_readback()
        self.assertEqual(integrity["integrity"], "VERIFIED")
        self.assertTrue(integrity["lock_identity_pinned_for_critical_section"])
        self.assertTrue(integrity["lock_identity_revalidated_before_commit"])
        self.assertFalse(
            integrity["process_local_fallback_grants_live_authority"]
        )
        self.assertEqual(
            plane.governed_authority_readback()["canonical_class"],
            "IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane",
        )

    def test_lock_path_replacement_rolls_back_before_commit(self) -> None:
        plane, receipt = self._quote_plane()
        before_state = plane._read_state()
        before_governance = plane._read_governance_state()
        original = plane._seal_state_object

        def replace_lock_after_state_mutation(*args, **kwargs):
            result = original(*args, **kwargs)
            plane.action_coordination_lock_path.unlink()
            plane.action_coordination_lock_path.write_text(
                "replacement inode\n", encoding="utf-8"
            )
            os.chmod(plane.action_coordination_lock_path, 0o600)
            return result

        plane._seal_state_object = replace_lock_after_state_mutation
        with self.assertRaisesRegex(RuntimeError, "coordination lock"):
            plane.approve_quote(
                "QUOTE-INTEGRITY",
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )

        self.assertEqual(plane._read_state(), before_state)
        self.assertEqual(plane._read_governance_state(), before_governance)
        events = plane._transaction_events()
        self.assertEqual(
            [event["event"] for event in events],
            ["ACTION_PREPARED", "ACTION_ROLLED_BACK"],
        )
        self.assertNotEqual(events[-1].get("failure_class"), None)

    def test_live_profile_fails_closed_without_provider_process_lock(self) -> None:
        with patch("authority_action_coordination_integrity.fcntl", None):
            with self.assertRaisesRegex(
                RuntimeError, "provider-process POSIX coordination"
            ):
                IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane(
                    self.root,
                    authority_snapshot=self.value,
                    authority_profile="LIVE_PROVIDER_AUTHORITY",
                )

    def test_mock_profile_can_use_process_local_fallback(self) -> None:
        with patch("authority_action_coordination_integrity.fcntl", None):
            plane = IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                authority_profile="MOCK_PROVIDER_CONFORMANCE",
            )
            readback = plane.authority_action_coordination_integrity_readback()
            self.assertEqual(readback["integrity"], "VERIFIED")
            self.assertFalse(
                readback["process_local_fallback_grants_live_authority"]
            )

    def test_symlink_coordination_lock_is_rejected(self) -> None:
        target = self.root / "outside-lock-target"
        target.write_text("not a lock\n", encoding="utf-8")
        lock_path = self.root / (
            IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane
            .COORDINATION_LOCK_FILE
        )
        lock_path.symlink_to(target.name)
        with self.assertRaises((OSError, RuntimeError)):
            IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )

    def test_hard_linked_coordination_lock_is_rejected(self) -> None:
        lock_path = self.root / (
            IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane
            .COORDINATION_LOCK_FILE
        )
        lock_path.write_text("lock\n", encoding="utf-8")
        os.chmod(lock_path, 0o600)
        os.link(lock_path, self.root / "second-lock-link")
        with self.assertRaisesRegex(RuntimeError, "hard-link"):
            IdentityPinnedCoordinatedAuthoritySnapshotCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )


if __name__ == "__main__":
    unittest.main()
