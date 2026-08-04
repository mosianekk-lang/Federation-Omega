from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from authority_action_coordination import (
    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane,
)
from authority_action_idempotency import (
    IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


class AuthorityActionIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _quote_plane(self, quote_id: str = "QUOTE-IDEMPOTENCY"):
        bootstrap = IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane(
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
        plane = IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        return plane, receipt

    def test_exact_quote_retry_returns_original_commit_without_new_transaction(self) -> None:
        plane, receipt = self._quote_plane()
        first = plane.approve_quote(
            "QUOTE-IDEMPOTENCY",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        second = plane.approve_quote(
            "QUOTE-IDEMPOTENCY",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(first, second)
        events = plane._transaction_events()
        self.assertEqual([event["event"] for event in events], [
            "ACTION_PREPARED",
            "ACTION_COMMITTED",
        ])
        self.assertEqual(
            first["authority_action_idempotency"]["state"],
            "EXACT_REPLAY_SAFE",
        )
        self.assertEqual(plane.governed_authority_readback()["approval_count"], 1)

    def test_exact_retry_remains_safe_after_restart(self) -> None:
        plane, receipt = self._quote_plane("QUOTE-IDEMPOTENCY-RESTART")
        first = plane.approve_quote(
            "QUOTE-IDEMPOTENCY-RESTART",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        restarted = IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        second = restarted.approve_quote(
            "QUOTE-IDEMPOTENCY-RESTART",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(restarted._transaction_events()), 2)

    def test_conflicting_retry_is_rejected_before_authority_reuse(self) -> None:
        plane, receipt = self._quote_plane("QUOTE-IDEMPOTENCY-CONFLICT")
        plane.approve_quote(
            "QUOTE-IDEMPOTENCY-CONFLICT",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        state = plane._read_state()
        state["quotes"]["QUOTE-IDEMPOTENCY-CONFLICT"]["amount"] = 570000.0
        plane._write_state(state)
        with self.assertRaisesRegex(ValueError, "idempotency conflict"):
            plane.approve_quote(
                "QUOTE-IDEMPOTENCY-CONFLICT",
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )
        self.assertEqual(len(plane._transaction_events()), 2)

    def test_tampered_idempotency_seal_fails_closed(self) -> None:
        plane, receipt = self._quote_plane("QUOTE-IDEMPOTENCY-TAMPER")
        plane.approve_quote(
            "QUOTE-IDEMPOTENCY-TAMPER",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        state = plane._read_state()
        state["quotes"]["QUOTE-IDEMPOTENCY-TAMPER"][
            "authority_action_idempotency"
        ]["intent_sha256"] = "0" * 64
        plane._write_state(state)
        with self.assertRaisesRegex(RuntimeError, "seal hash invalid"):
            plane.authority_action_idempotency_readback()

    def test_historical_v9_commit_without_seal_is_not_replayed(self) -> None:
        quote_id = "QUOTE-IDEMPOTENCY-LEGACY"
        bootstrap = CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        bootstrap.create_lead("LEAD-IDEMPOTENCY-LEGACY", "org", "inbound", "delay")
        bootstrap.create_quote_draft(
            quote_id,
            "LEAD-IDEMPOTENCY-LEGACY",
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
        legacy = CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        legacy.approve_quote(
            quote_id,
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        current = IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        with self.assertRaisesRegex(RuntimeError, "lacks an idempotency seal"):
            current.approve_quote(
                quote_id,
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )

    def test_readback_projects_v10_canonical_state(self) -> None:
        plane, receipt = self._quote_plane("QUOTE-IDEMPOTENCY-READBACK")
        plane.approve_quote(
            "QUOTE-IDEMPOTENCY-READBACK",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        readback = plane.governed_authority_readback()
        self.assertEqual(
            readback["canonical_class"],
            "IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane",
        )
        idempotency = readback["authority_action_idempotency"]
        self.assertEqual(idempotency["integrity"], "VERIFIED")
        self.assertTrue(idempotency["exact_retry_returns_committed_record"])
        self.assertFalse(idempotency["retry_consumes_owner_authority_again"])
        self.assertEqual(idempotency["sealed_objects"]["quote_approval"], 1)


if __name__ == "__main__":
    unittest.main()
