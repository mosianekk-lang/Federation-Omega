from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from authority_action_crash_recovery import (
    CrashSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_action_journal import (
    JournalSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


class AuthorityActionJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _quote_plane(self, quote_id: str = "QUOTE-JOURNAL"):
        bootstrap = JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
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
        plane = JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        return plane, receipt

    def _prepare_unterminated_quote_transaction(self, plane, quote_id: str):
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
                "object_id": quote_id,
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

    def test_successful_action_uses_atomic_event_files(self) -> None:
        plane, receipt = self._quote_plane()
        quote = plane.approve_quote(
            "QUOTE-JOURNAL",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(
            quote["authority_action_commit"]["state"],
            "ATOMIC_AUTHORITY_ACTION_COMMITTED",
        )
        readback = plane.authority_action_transaction_readback()
        journal = readback["transaction_journal"]
        self.assertEqual(journal["legacy_jsonl_events"], 0)
        self.assertEqual(journal["atomically_published_events"], 2)
        self.assertEqual(journal["total_events"], 2)
        self.assertEqual(journal["incomplete_publications"], [])
        self.assertTrue(journal["event_file_hash_bound"])
        self.assertTrue(journal["atomic_rename_publication"])
        self.assertFalse(
            readback["torn_transaction_event_visible_after_process_crash"]
        )
        self.assertFalse(plane.transaction_file.exists())

    def test_restart_removes_incomplete_publication_before_new_work(self) -> None:
        plane, receipt = self._quote_plane()
        temporary = plane.transaction_journal_root / ".00000001.partial.tmp"
        temporary.write_text('{"sequence":1', encoding="utf-8")
        restarted = JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertFalse(temporary.exists())
        journal = restarted.authority_action_journal_readback()
        self.assertEqual(journal["total_events"], 0)
        self.assertEqual(journal["incomplete_publications"], [])
        self.assertEqual(
            restarted.governed_authority_readback()["revenue"][
                "live_verified_revenue_events"
            ],
            0,
        )

    def test_restart_rolls_back_when_terminal_publication_never_completed(self) -> None:
        plane, receipt = self._quote_plane()
        before_state = plane._read_state()
        before_governance = plane._read_governance_state()
        transaction = self._prepare_unterminated_quote_transaction(
            plane, "QUOTE-JOURNAL"
        )

        partial_state = plane._read_state()
        partial_state["quotes"]["QUOTE-JOURNAL"]["status"] = "APPROVED"
        partial_state["quotes"]["QUOTE-JOURNAL"]["torn_commit_simulation"] = True
        plane._write_state(partial_state)
        partial_governance = plane._read_governance_state()
        partial_governance["consumed_owner_receipts"][receipt.receipt_id] = {
            "torn_commit_simulation": True
        }
        plane._write_governance_state(partial_governance)
        temporary = plane.transaction_journal_root / ".terminal.event.tmp"
        temporary.write_text('{"event":"ACTION_COMMITTED"', encoding="utf-8")

        restarted = JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertEqual(restarted._read_state(), before_state)
        self.assertEqual(restarted._read_governance_state(), before_governance)
        events = restarted._transaction_events()
        self.assertEqual([event["event"] for event in events], [
            "ACTION_PREPARED",
            "ACTION_ROLLED_BACK",
        ])
        self.assertEqual(events[-1]["transaction_id"], transaction["transaction_id"])
        self.assertEqual(
            events[-1]["failure_class"], "PROCESS_RESTART_RECOVERY"
        )
        journal = restarted.authority_action_journal_readback()
        self.assertEqual(journal["atomically_published_events"], 2)
        self.assertEqual(journal["incomplete_publications"], [])

    def test_tampered_published_event_fails_closed(self) -> None:
        plane, receipt = self._quote_plane()
        plane.approve_quote(
            "QUOTE-JOURNAL",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        first = sorted(plane.transaction_journal_root.iterdir())[0]
        event = json.loads(first.read_text(encoding="utf-8"))
        event["object_id"] = "QUOTE-TAMPERED"
        first.write_text(json.dumps(event) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "hash binding invalid"):
            JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                owner_receipts={receipt.receipt_id: receipt},
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )

    def test_legacy_jsonl_prefix_remains_valid_and_new_events_continue_chain(self) -> None:
        legacy = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        legacy.create_lead("LEAD-LEGACY", "org", "inbound", "manual delay")
        legacy.create_quote_draft(
            "QUOTE-LEGACY",
            "LEAD-LEGACY",
            "AO-PILOT",
            "ZAR",
            560000.0,
            12,
        )
        legacy_subject = legacy.quote_authority_subject("QUOTE-LEGACY")
        legacy_receipt = owner_receipt(
            "OWNER-QUOTE-LEGACY",
            gate=legacy_subject["gate"],
            evidence_id=legacy_subject["evidence_id"],
            content_sha256=legacy_subject["content_sha256"],
        )
        legacy = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={legacy_receipt.receipt_id: legacy_receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        legacy.approve_quote(
            "QUOTE-LEGACY",
            owner_decision_receipt_id=legacy_receipt.receipt_id,
            now=NOW,
        )
        legacy.create_lead("LEAD-NEXT", "org", "inbound", "manual delay")
        legacy.create_quote_draft(
            "QUOTE-NEXT", "LEAD-NEXT", "AO-PILOT", "ZAR", 560000.0, 12
        )
        subject = legacy.quote_authority_subject("QUOTE-NEXT")
        receipt = owner_receipt(
            "OWNER-QUOTE-NEXT",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )

        plane = JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.approve_quote(
            "QUOTE-NEXT",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        events = plane._transaction_events()
        self.assertEqual([event["sequence"] for event in events], [1, 2, 3, 4])
        self.assertEqual(
            events[2]["previous_event_sha256"], events[1]["event_sha256"]
        )
        journal = plane.authority_action_journal_readback()
        self.assertEqual(journal["legacy_jsonl_events"], 2)
        self.assertEqual(journal["atomically_published_events"], 2)
        self.assertTrue(journal["legacy_prefix_frozen"])


if __name__ == "__main__":
    unittest.main()
