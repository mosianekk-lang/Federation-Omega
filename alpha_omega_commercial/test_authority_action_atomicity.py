from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from authority_action_atomicity import (
    AtomicAuthoritySnapshotCommercialControlPlane,
)
from test_authority_snapshot_action_binding import (
    NOW,
    owner_receipt,
    snapshot,
)


class AuthorityActionAtomicityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _quote_plane(self):
        bootstrap = AtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        bootstrap.create_lead("LEAD-ATOMIC", "org", "inbound", "manual delay")
        bootstrap.create_quote_draft(
            "QUOTE-ATOMIC",
            "LEAD-ATOMIC",
            "AO-PILOT",
            "ZAR",
            560000.0,
            12,
        )
        subject = bootstrap.quote_authority_subject("QUOTE-ATOMIC")
        receipt = owner_receipt(
            "OWNER-QUOTE-ATOMIC",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = AtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        return plane, receipt

    def test_successful_quote_has_atomic_commit_and_exact_binding(self) -> None:
        plane, receipt = self._quote_plane()
        quote = plane.approve_quote(
            "QUOTE-ATOMIC",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        binding = quote["authority_snapshot_binding"]
        commit = quote["authority_action_commit"]
        self.assertEqual(commit["state"], "ATOMIC_AUTHORITY_ACTION_COMMITTED")
        self.assertEqual(
            commit["transaction_id"],
            binding["atomic_transaction_id"],
        )
        self.assertEqual(
            commit["acceptance_entry_sha256"],
            binding["acceptance_entry_sha256"],
        )
        readback = plane.authority_action_transaction_readback()
        self.assertEqual(readback["prepared"], 1)
        self.assertEqual(readback["committed"], 1)
        self.assertEqual(readback["rolled_back"], 0)
        self.assertEqual(readback["unterminated"], [])
        self.assertTrue(readback["provider_authority_held_for_full_action"])

    def test_binding_failure_restores_state_and_owner_receipt_consumption(self) -> None:
        plane, receipt = self._quote_plane()
        before_state = plane._read_state()
        before_governance = plane._read_governance_state()

        def fail_binding(**_: object):
            raise RuntimeError("injected binding persistence failure")

        plane._bind_state_object = fail_binding  # type: ignore[method-assign]
        with self.assertRaisesRegex(RuntimeError, "injected binding"):
            plane.approve_quote(
                "QUOTE-ATOMIC",
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )

        self.assertEqual(plane._read_state(), before_state)
        self.assertEqual(plane._read_governance_state(), before_governance)
        self.assertNotIn(
            receipt.receipt_id,
            plane._read_governance_state()["consumed_owner_receipts"],
        )
        readback = plane.authority_action_transaction_readback()
        self.assertEqual(readback["prepared"], 1)
        self.assertEqual(readback["committed"], 0)
        self.assertEqual(readback["rolled_back"], 1)
        self.assertEqual(readback["unterminated"], [])
        self.assertFalse(readback["partial_state_visible_after_rollback"])

    def test_restart_preserves_commit_and_transaction_integrity(self) -> None:
        plane, receipt = self._quote_plane()
        original = plane.approve_quote(
            "QUOTE-ATOMIC",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        restarted = AtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        stored = restarted._read_state()["quotes"]["QUOTE-ATOMIC"]
        self.assertEqual(
            stored["authority_action_commit"],
            original["authority_action_commit"],
        )
        self.assertEqual(
            restarted.authority_action_transaction_readback()["integrity"],
            "VERIFIED",
        )
        governed = restarted.governed_authority_readback()
        self.assertEqual(
            governed["canonical_class"],
            "AtomicAuthoritySnapshotCommercialControlPlane",
        )
        self.assertEqual(
            governed["revenue"]["live_verified_revenue_events"],
            0,
        )

    def test_transaction_ledger_tampering_fails_closed(self) -> None:
        plane, receipt = self._quote_plane()
        plane.approve_quote(
            "QUOTE-ATOMIC",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        lines = plane.transaction_file.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["object_id"] = "TAMPERED"
        lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
        plane.transaction_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "transaction hash invalid"):
            AtomicAuthoritySnapshotCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                owner_receipts={receipt.receipt_id: receipt},
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )

    def test_reference_profile_does_not_claim_atomic_live_authority(self) -> None:
        plane = AtomicAuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=None,
            authority_profile="REFERENCE_PROVIDER",
        )
        plane.create_lead("LEAD-REF", "org", "inbound", "manual delay")
        quote = plane.create_quote_draft(
            "QUOTE-REF", "LEAD-REF", "AO-PILOT", "ZAR", 1000.0, 1
        )
        self.assertNotIn("authority_action_commit", quote)
        readback = plane.authority_action_transaction_readback()
        self.assertEqual(readback["events"], 0)


if __name__ == "__main__":
    unittest.main()
