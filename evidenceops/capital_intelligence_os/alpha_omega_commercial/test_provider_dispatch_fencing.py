from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from authority_snapshot import parse_utc
from provider_dispatch_fencing import (
    FencedConformantMockProviderAdapter,
    FencedProviderDispatchCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


class ProviderDispatchFencingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plane_with_dispatch(self, object_id: str):
        bootstrap = FencedProviderDispatchCommercialControlPlane(
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
        plane = FencedProviderDispatchCommercialControlPlane(
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
            operation="dry_run_provider_fencing_contract",
            payload={"object_id": object_id, "mode": "fencing-conformance-only"},
            now=NOW,
        )
        return plane, owner, prepared

    def test_renewal_extends_lease_and_blocks_original_expiry_takeover(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-FENCE-RENEW")
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=5, now=NOW
        )
        renewed = plane.renew_provider_dispatch_claim(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            lease_seconds=10,
            now=shift(4),
        )
        self.assertEqual(renewed["lease_expires_at"], shift(14))
        with self.assertRaisesRegex(RuntimeError, "another worker"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(6)
            )
        takeover = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(15)
        )
        self.assertEqual(takeover["attempt"], 2)

    def test_started_attempt_is_idempotent_and_envelope_is_hash_bound(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-FENCE-START")
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=NOW
        )
        started = plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(1)
        )
        retry = plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
        )
        self.assertEqual(started, retry)
        envelope = plane.provider_dispatch_attempt_envelope(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
        )
        self.assertEqual(envelope["fencing_epoch"], 1)
        self.assertEqual(
            envelope["dispatch_attempt_reference"], started["dispatch_attempt_reference"]
        )
        receipt = FencedConformantMockProviderAdapter("reference_provider").execute(envelope)
        self.assertEqual(receipt["fencing_epoch"], 1)

    def test_stale_attempt_receipt_is_rejected_after_takeover(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-FENCE-STALE")
        adapter = FencedConformantMockProviderAdapter("reference_provider")
        first = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=5, now=NOW
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=first["claim_token"], now=shift(1)
        )
        first_envelope = plane.provider_dispatch_attempt_envelope(
            prepared["dispatch_id"], claim_token=first["claim_token"], now=shift(1)
        )
        first_receipt = adapter.execute(first_envelope)
        second = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(6)
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=second["claim_token"], now=shift(7)
        )
        with self.assertRaisesRegex(RuntimeError, "current fenced attempt"):
            plane.admit_provider_dispatch_receipt(
                prepared["dispatch_id"],
                first_receipt,
                claim_token=second["claim_token"],
                now=shift(8),
            )
        second_envelope = plane.provider_dispatch_attempt_envelope(
            prepared["dispatch_id"], claim_token=second["claim_token"], now=shift(8)
        )
        second_receipt = adapter.execute(second_envelope)
        admitted = plane.admit_provider_dispatch_receipt(
            prepared["dispatch_id"],
            second_receipt,
            claim_token=second["claim_token"],
            now=shift(9),
        )
        self.assertEqual(admitted["provider_receipt"]["fencing_epoch"], 2)

    def test_terminal_failure_releases_claim_for_higher_fencing_epoch(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-FENCE-FAIL")
        first = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=NOW
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=first["claim_token"], now=shift(1)
        )
        plane.record_provider_dispatch_attempt_failure(
            prepared["dispatch_id"],
            claim_token=first["claim_token"],
            error_class="TRANSIENT_PROVIDER_TIMEOUT",
            retryable=True,
            now=shift(2),
        )
        second = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(3)
        )
        started = plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=second["claim_token"], now=shift(4)
        )
        self.assertEqual(second["attempt"], 2)
        self.assertEqual(started["fencing_epoch"], 2)

    def test_completion_binding_survives_restart(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-FENCE-RESTART")
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=NOW
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(1)
        )
        envelope = plane.provider_dispatch_attempt_envelope(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
        )
        receipt = FencedConformantMockProviderAdapter("reference_provider").execute(envelope)
        admitted = plane.admit_provider_dispatch_receipt(
            prepared["dispatch_id"], receipt, claim_token=claim["claim_token"], now=shift(3)
        )
        restarted = FencedProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertEqual(
            admitted,
            restarted.admit_provider_dispatch_receipt(
                prepared["dispatch_id"], receipt, claim_token=claim["claim_token"], now=shift(4)
            ),
        )
        readback = restarted.provider_dispatch_attempt_readback()
        self.assertEqual(readback["completed_attempts"], 1)
        self.assertFalse(readback["provider_native_fencing_proven"])

    def test_fencing_event_tamper_fails_closed(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-FENCE-TAMPER")
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=60, now=NOW
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(1)
        )
        state = plane._read_state()
        state["provider_dispatch_claim_history"][prepared["dispatch_id"]][1][
            "fencing_epoch"
        ] = 99
        plane._write_state(state)
        with self.assertRaisesRegex(RuntimeError, "event hash invalid"):
            plane.provider_dispatch_attempt_readback()


if __name__ == "__main__":
    unittest.main()
