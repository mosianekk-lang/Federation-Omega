from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from authority_snapshot import parse_utc
from provider_dispatch_claim_lease import LeasedProviderDispatchOutboxCommercialControlPlane
from provider_dispatch_outbox import ConformantMockProviderAdapter
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


class ProviderDispatchClaimLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plane_with_dispatch(self, object_id: str):
        bootstrap = LeasedProviderDispatchOutboxCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        lead_id = object_id.replace("QUOTE", "LEAD")
        bootstrap.create_lead(lead_id, "org", "inbound", "delay")
        bootstrap.create_quote_draft(object_id, lead_id, "AO-PILOT", "ZAR", 560000.0, 12)
        subject = bootstrap.quote_authority_subject(object_id)
        owner = owner_receipt(
            "OWNER-" + object_id,
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = LeasedProviderDispatchOutboxCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.approve_quote(object_id, owner_decision_receipt_id=owner.receipt_id, now=NOW)
        prepared = plane.prepare_provider_dispatch(
            action="quote_approval",
            object_id=object_id,
            provider_domain="reference_provider",
            operation="dry_run_provider_contract",
            payload={"object_id": object_id, "mode": "conformance-only"},
            now=NOW,
        )
        return plane, owner, prepared

    def test_same_worker_retry_is_idempotent_and_other_worker_is_blocked(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-LEASE")
        first = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=NOW
        )
        self.assertEqual(
            first,
            plane.claim_provider_dispatch(
                prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=shift(1)
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "another worker"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(2)
            )

    def test_expired_lease_can_be_taken_over_and_stale_token_is_rejected(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-LEASE-TAKEOVER")
        first = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=5, now=NOW
        )
        second = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(6)
        )
        self.assertNotEqual(first["claim_token"], second["claim_token"])
        receipt = ConformantMockProviderAdapter("reference_provider").execute(prepared)
        with self.assertRaisesRegex(RuntimeError, "not current"):
            plane.admit_provider_dispatch_receipt(
                prepared["dispatch_id"], receipt, claim_token=first["claim_token"], now=shift(7)
            )

    def test_receipt_requires_current_claim_and_survives_restart(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-LEASE-RESTART")
        receipt = ConformantMockProviderAdapter("reference_provider").execute(prepared)
        with self.assertRaisesRegex(RuntimeError, "requires a current claim token"):
            plane.admit_provider_dispatch_receipt(prepared["dispatch_id"], receipt)
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=NOW
        )
        admitted = plane.admit_provider_dispatch_receipt(
            prepared["dispatch_id"], receipt, claim_token=claim["claim_token"], now=shift(1)
        )
        restarted = LeasedProviderDispatchOutboxCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertEqual(
            admitted,
            restarted.admit_provider_dispatch_receipt(
                prepared["dispatch_id"], receipt, claim_token=claim["claim_token"], now=shift(2)
            ),
        )
        readback = restarted.provider_dispatch_claim_readback()
        self.assertEqual(readback["completed_claims"], 1)
        self.assertEqual(readback["active_claims"], 0)
        self.assertFalse(readback["distributed_provider_exactly_once_proven"])

    def test_abandoned_claim_allows_immediate_reclaim(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-LEASE-ABANDON")
        first = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=NOW
        )
        plane.abandon_provider_dispatch_claim(
            prepared["dispatch_id"], claim_token=first["claim_token"], now=shift(1)
        )
        second = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(2)
        )
        self.assertEqual(second["attempt"], 2)

    def test_claim_history_tamper_fails_closed(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-LEASE-TAMPER")
        plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=NOW
        )
        state = plane._read_state()
        state["provider_dispatch_claim_history"][prepared["dispatch_id"]][0]["worker_id"] = "changed"
        plane._write_state(state)
        with self.assertRaisesRegex(RuntimeError, "event hash invalid"):
            plane.provider_dispatch_claim_readback()


if __name__ == "__main__":
    unittest.main()
