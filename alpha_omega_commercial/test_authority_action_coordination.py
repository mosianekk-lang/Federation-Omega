from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from authority_action_coordination import (
    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


class AuthorityActionCoordinationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _quote_plane(self, quote_id: str = "QUOTE-COORDINATION"):
        bootstrap = CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
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
        plane = CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        return plane, receipt

    def _prepare_unterminated_quote_transaction(self, plane, quote_id: str):
        with plane._action_coordination_locked():
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

    def test_successful_quote_uses_coordinated_canonical_class(self) -> None:
        plane, receipt = self._quote_plane()
        quote = plane.approve_quote(
            "QUOTE-COORDINATION",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(
            quote["authority_action_commit"]["state"],
            "ATOMIC_AUTHORITY_ACTION_COMMITTED",
        )
        readback = plane.authority_action_transaction_readback()
        coordination = readback["process_coordination"]
        self.assertTrue(coordination["startup_recovery_serialized"])
        self.assertTrue(coordination["live_authority_actions_serialized"])
        self.assertFalse(
            coordination["concurrent_startup_can_rollback_live_transaction"]
        )
        self.assertEqual(
            plane.governed_authority_readback()["canonical_class"],
            "CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane",
        )

    def test_concurrent_startup_waits_for_live_transaction_terminal_event(self) -> None:
        plane, receipt = self._quote_plane()
        action = plane._atomic_action(
            stage="C13",
            action="quote_approval",
            object_id="QUOTE-COORDINATION",
            domains=("owner_decision",),
            now=NOW,
        )
        transaction = action.__enter__()
        started = threading.Event()
        finished = threading.Event()
        result: dict[str, object] = {}

        def restart_worker() -> None:
            started.set()
            try:
                result["plane"] = (
                    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
                        self.root,
                        authority_snapshot=self.value,
                        owner_receipts={receipt.receipt_id: receipt},
                        authority_profile="LIVE_PROVIDER_AUTHORITY",
                    )
                )
            except BaseException as exc:  # pragma: no cover - asserted below
                result["error"] = exc
            finally:
                finished.set()

        worker = threading.Thread(target=restart_worker, daemon=True)
        worker.start()
        self.assertTrue(started.wait(1.0))
        self.assertFalse(finished.wait(0.2))
        action.__exit__(None, None, None)
        self.assertTrue(finished.wait(3.0))
        worker.join(timeout=1.0)
        self.assertNotIn("error", result)
        restarted = result["plane"]
        events = restarted._transaction_events()
        self.assertEqual(
            [event["event"] for event in events],
            ["ACTION_PREPARED", "ACTION_COMMITTED"],
        )
        self.assertEqual(events[0]["transaction_id"], transaction["transaction_id"])
        self.assertEqual(events[1]["transaction_id"], transaction["transaction_id"])
        self.assertEqual(
            restarted.authority_action_recovery_readback()[
                "unterminated_transactions"
            ],
            [],
        )

    def test_released_lock_allows_real_crash_recovery_before_new_work(self) -> None:
        plane, receipt = self._quote_plane()
        before_state = plane._read_state()
        before_governance = plane._read_governance_state()
        transaction = self._prepare_unterminated_quote_transaction(
            plane, "QUOTE-COORDINATION"
        )
        partial_state = plane._read_state()
        partial_state["quotes"]["QUOTE-COORDINATION"]["status"] = "APPROVED"
        partial_state["quotes"]["QUOTE-COORDINATION"]["partial_worker"] = True
        plane._write_state(partial_state)
        partial_governance = plane._read_governance_state()
        partial_governance["consumed_owner_receipts"][receipt.receipt_id] = {
            "partial_worker": True
        }
        plane._write_governance_state(partial_governance)

        restarted = CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertEqual(restarted._read_state(), before_state)
        self.assertEqual(restarted._read_governance_state(), before_governance)
        events = restarted._transaction_events()
        self.assertEqual(
            [event["event"] for event in events],
            ["ACTION_PREPARED", "ACTION_ROLLED_BACK"],
        )
        self.assertEqual(events[-1]["transaction_id"], transaction["transaction_id"])
        self.assertEqual(
            events[-1]["failure_class"], "PROCESS_RESTART_RECOVERY"
        )

    def test_integrity_readback_is_reentrant_and_serialized(self) -> None:
        plane, _ = self._quote_plane()
        with plane._action_coordination_locked():
            coordination = plane.authority_action_coordination_readback()
            transaction = plane.authority_action_transaction_readback()
            authority = plane.governed_authority_readback()
        self.assertEqual(coordination["integrity"], "VERIFIED")
        self.assertEqual(
            transaction["process_coordination"]["integrity"], "VERIFIED"
        )
        self.assertEqual(
            authority["authority_action_process_coordination"]["integrity"],
            "VERIFIED",
        )

    def test_invalid_coordination_lock_path_fails_closed(self) -> None:
        lock_path = self.root / (
            CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane.
            COORDINATION_LOCK_FILE
        )
        lock_path.mkdir(parents=True)
        with self.assertRaises(OSError):
            CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )


if __name__ == "__main__":
    unittest.main()
