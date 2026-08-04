from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from provider_dispatch_outbox import (
    ConformantMockProviderAdapter,
    LIVE_PROVIDER_RECEIPT_CLASS,
    ProviderDispatchOutboxCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


class ProviderDispatchOutboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plane_with_local_commit(self, object_id: str):
        bootstrap = ProviderDispatchOutboxCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        lead_id = object_id.replace("QUOTE", "LEAD")
        bootstrap.create_lead(lead_id, "org", "inbound", "delay")
        bootstrap.create_quote_draft(
            object_id, lead_id, "AO-PILOT", "ZAR", 560000.0, 12
        )
        subject = bootstrap.quote_authority_subject(object_id)
        receipt = owner_receipt(
            "OWNER-" + object_id,
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = ProviderDispatchOutboxCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.approve_quote(
            object_id,
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        return plane, receipt

    def prepare(self, plane, object_id: str):
        return plane.prepare_provider_dispatch(
            action="quote_approval",
            object_id=object_id,
            provider_domain="reference_provider",
            operation="dry_run_provider_contract",
            payload={"object_id": object_id, "mode": "conformance-only"},
            now=NOW,
        )

    def test_prepare_and_mock_receipt_are_idempotent(self) -> None:
        plane, _ = self.plane_with_local_commit("QUOTE-DISPATCH")
        first = self.prepare(plane, "QUOTE-DISPATCH")
        self.assertEqual(first, self.prepare(plane, "QUOTE-DISPATCH"))
        adapter = ConformantMockProviderAdapter("reference_provider")
        receipt = adapter.execute(first)
        self.assertEqual(receipt, adapter.execute(first))
        admitted = plane.admit_provider_dispatch_receipt(first["dispatch_id"], receipt)
        self.assertEqual(
            admitted,
            plane.admit_provider_dispatch_receipt(first["dispatch_id"], receipt),
        )
        self.assertFalse(receipt["external_mutation_performed"])

    def test_changed_payload_for_same_provider_command_is_rejected(self) -> None:
        object_id = "QUOTE-DISPATCH-CONFLICT"
        plane, _ = self.plane_with_local_commit(object_id)
        prepared = self.prepare(plane, object_id)
        with self.assertRaisesRegex(ValueError, "provider dispatch conflict"):
            plane.prepare_provider_dispatch(
                action="quote_approval",
                object_id=object_id,
                provider_domain="reference_provider",
                operation="dry_run_provider_contract",
                payload={"object_id": object_id, "mode": "changed-command"},
                now=NOW,
            )
        self.assertEqual(
            list(plane._read_state()["provider_dispatches"]),
            [prepared["dispatch_id"]],
        )

    def test_receipt_survives_restart(self) -> None:
        plane, owner = self.plane_with_local_commit("QUOTE-DISPATCH-RESTART")
        prepared = self.prepare(plane, "QUOTE-DISPATCH-RESTART")
        receipt = ConformantMockProviderAdapter("reference_provider").execute(prepared)
        admitted = plane.admit_provider_dispatch_receipt(prepared["dispatch_id"], receipt)
        restarted = ProviderDispatchOutboxCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertEqual(
            admitted,
            restarted.admit_provider_dispatch_receipt(prepared["dispatch_id"], receipt),
        )

    def test_live_receipt_is_held_without_native_verifier(self) -> None:
        plane, _ = self.plane_with_local_commit("QUOTE-DISPATCH-LIVE")
        prepared = self.prepare(plane, "QUOTE-DISPATCH-LIVE")
        with self.assertRaisesRegex(RuntimeError, "provider-native verifier"):
            plane.admit_provider_dispatch_receipt(
                prepared["dispatch_id"],
                {
                    "receipt_class": LIVE_PROVIDER_RECEIPT_CLASS,
                    "dispatch_id": prepared["dispatch_id"],
                },
            )

    def test_tamper_fails_closed_and_truth_is_preserved(self) -> None:
        plane, _ = self.plane_with_local_commit("QUOTE-DISPATCH-TAMPER")
        prepared = self.prepare(plane, "QUOTE-DISPATCH-TAMPER")
        receipt = ConformantMockProviderAdapter("reference_provider").execute(prepared)
        plane.admit_provider_dispatch_receipt(prepared["dispatch_id"], receipt)
        readback = plane.provider_dispatch_readback()
        self.assertEqual(readback["mock_conformance_receipts"], 1)
        self.assertEqual(readback["live_provider_receipts"], 0)
        self.assertFalse(readback["distributed_provider_exactly_once_proven"])
        state = plane._read_state()
        state["provider_dispatches"][prepared["dispatch_id"]]["operation"] = "changed"
        plane._write_state(state)
        with self.assertRaisesRegex(RuntimeError, "record hash invalid"):
            plane.provider_dispatch_readback()


if __name__ == "__main__":
    unittest.main()
