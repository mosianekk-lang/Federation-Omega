from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from authority_action_crash_recovery import (
    CrashSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


class AuthorityActionCrashRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _quote_plane(self):
        bootstrap = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        bootstrap.create_lead("LEAD-CRASH", "org", "inbound", "manual delay")
        bootstrap.create_quote_draft(
            "QUOTE-CRASH",
            "LEAD-CRASH",
            "AO-PILOT",
            "ZAR",
            560000.0,
            12,
        )
        subject = bootstrap.quote_authority_subject("QUOTE-CRASH")
        receipt = owner_receipt(
            "OWNER-QUOTE-CRASH",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        return plane, receipt

    def _prepare_unterminated_quote_transaction(self, plane):
        plane.accept_authority_snapshot(now=NOW)
        ledger = plane.authority_snapshot_acceptance
        with ledger._locked():
            entry = plane._latest_locked_acceptance(now=NOW)
            current = plane.authority_snapshot_validator.snapshot
            self.assertIsNotNone(current)
            events = plane._transaction_events()
            transaction = {
                "transaction_id": f"AO-ACTION-{len(events) + 1:08d}",
                "stage": "C13",
                "action": "quote_approval",
                "object_id": "QUOTE-CRASH",
                "snapshot_id": current.snapshot_id,
                "snapshot_sha256": current.snapshot_sha256,
                "acceptance_sequence": entry["sequence"],
                "acceptance_entry_sha256": entry["entry_sha256"],
                "domains": ["owner_decision"],
                "recorded_at": NOW,
            }
            backup = plane._capture_transaction_files()
            plane._prepare_recovery_bundle(transaction, backup)
            plane._append_transaction_event("ACTION_PREPARED", transaction)
        return transaction

    def test_restart_recovers_unterminated_transaction_before_new_action(self) -> None:
        plane, receipt = self._quote_plane()
        before_state = plane._read_state()
        before_governance = plane._read_governance_state()
        transaction = self._prepare_unterminated_quote_transaction(plane)

        partial_state = plane._read_state()
        partial_state["quotes"]["QUOTE-CRASH"]["status"] = "APPROVED"
        partial_state["quotes"]["QUOTE-CRASH"]["process_crash_partial"] = True
        plane._write_state(partial_state)
        partial_governance = plane._read_governance_state()
        partial_governance["consumed_owner_receipts"][receipt.receipt_id] = {
            "process_crash_partial": True
        }
        plane._write_governance_state(partial_governance)

        restarted = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertEqual(restarted._read_state(), before_state)
        self.assertEqual(restarted._read_governance_state(), before_governance)
        readback = restarted.authority_action_transaction_readback()
        self.assertEqual(readback["prepared"], 1)
        self.assertEqual(readback["committed"], 0)
        self.assertEqual(readback["rolled_back"], 1)
        self.assertEqual(readback["unterminated"], [])
        recovery = readback["process_crash_recovery"]
        self.assertEqual(recovery["process_restart_recoveries"], 1)
        self.assertEqual(recovery["durable_recovery_bundles"], [])
        self.assertEqual(
            restarted._transaction_events()[-1]["failure_class"],
            "PROCESS_RESTART_RECOVERY",
        )
        self.assertEqual(
            restarted._transaction_events()[-1]["transaction_id"],
            transaction["transaction_id"],
        )

    def test_tampered_recovery_content_fails_closed(self) -> None:
        plane, receipt = self._quote_plane()
        transaction = self._prepare_unterminated_quote_transaction(plane)
        bundle = plane._recovery_bundle(transaction["transaction_id"])
        manifest = json.loads(
            (bundle / plane.RECOVERY_MANIFEST).read_text(encoding="utf-8")
        )
        content_entry = next(entry for entry in manifest["entries"] if entry["existed"])
        content_path = bundle / content_entry["content_file"]
        content_path.write_bytes(content_path.read_bytes() + b"tamper")

        with self.assertRaisesRegex(RuntimeError, "content hash invalid"):
            CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                owner_receipts={receipt.receipt_id: receipt},
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )

    def test_successful_commit_removes_recovery_bundle(self) -> None:
        plane, receipt = self._quote_plane()
        quote = plane.approve_quote(
            "QUOTE-CRASH",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(
            quote["authority_action_commit"]["state"],
            "ATOMIC_AUTHORITY_ACTION_COMMITTED",
        )
        recovery = plane.authority_action_recovery_readback()
        self.assertEqual(recovery["durable_recovery_bundles"], [])
        self.assertEqual(recovery["unterminated_transactions"], [])
        self.assertTrue(recovery["recovery_manifest_hash_bound"])
        self.assertTrue(recovery["recovery_content_hash_verified"])

    def test_orphan_bundle_is_removed_without_promoting_authority(self) -> None:
        plane, receipt = self._quote_plane()
        orphan = plane.recovery_root / "AO-ACTION-ORPHAN"
        orphan.mkdir(parents=True)
        (orphan / "unused").write_text("orphan", encoding="utf-8")
        restarted = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertFalse(orphan.exists())
        self.assertEqual(
            restarted.authority_action_transaction_readback()["events"],
            0,
        )
        self.assertEqual(
            restarted.governed_authority_readback()["revenue"][
                "live_verified_revenue_events"
            ],
            0,
        )

    def test_reference_profile_does_not_create_recovery_bundle(self) -> None:
        plane = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=None,
            authority_profile="REFERENCE_PROVIDER",
        )
        plane.create_lead("LEAD-REF", "org", "inbound", "manual delay")
        quote = plane.create_quote_draft(
            "QUOTE-REF", "LEAD-REF", "AO-PILOT", "ZAR", 1000.0, 1
        )
        self.assertNotIn("authority_action_commit", quote)
        self.assertEqual(
            plane.authority_action_recovery_readback()[
                "durable_recovery_bundles"
            ],
            [],
        )


if __name__ == "__main__":
    unittest.main()
