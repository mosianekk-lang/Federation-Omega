from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from authority_snapshot import parse_utc
from provider_dispatch_outcome_reconciliation import (
    OUTCOME_COMPLETED,
    OUTCOME_NO_EFFECT,
    OutcomeReconciledProviderDispatchCommercialControlPlane,
    ReconciliationConformantMockProviderAdapter,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


class ProviderDispatchOutcomeReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plane_with_dispatch(self, object_id: str):
        bootstrap = OutcomeReconciledProviderDispatchCommercialControlPlane(
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
        owner = owner_receipt(
            "OWNER-" + object_id,
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = OutcomeReconciledProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.approve_quote(
            object_id, owner_decision_receipt_id=owner.receipt_id, now=NOW
        )
        prepared = plane.prepare_provider_dispatch(
            action="quote_approval",
            object_id=object_id,
            provider_domain="reference_provider",
            operation="dry_run_provider_outcome_reconciliation_contract",
            payload={"object_id": object_id, "mode": "reconciliation-only"},
            now=NOW,
        )
        return plane, owner, prepared

    def begin(self, plane, prepared, *, worker="worker-a", lease=5):
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id=worker, lease_seconds=lease, now=NOW
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(1)
        )
        envelope = plane.provider_dispatch_attempt_envelope(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(1)
        )
        return claim, envelope

    def test_pre_submission_expiry_still_allows_takeover(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-OUTCOME-PRE")
        first = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-a", lease_seconds=5, now=NOW
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=first["claim_token"], now=shift(1)
        )
        second = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(6)
        )
        self.assertEqual(second["attempt"], 2)

    def test_submitted_expiry_is_quarantined_and_blocks_takeover(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-OUTCOME-QUARANTINE")
        claim, _ = self.begin(plane, prepared)
        submitted = plane.record_provider_dispatch_submission(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
        )
        self.assertEqual(submitted["event_type"], "SUBMITTED")
        with self.assertRaisesRegex(RuntimeError, "reconciliation required"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(6)
            )
        with self.assertRaisesRegex(RuntimeError, "reconciliation required"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"], worker_id="worker-c", lease_seconds=60, now=shift(7)
            )
        self.assertEqual(plane.provider_dispatch_outcome_readback()["unresolved_outcomes"], 1)

    def test_submitted_attempt_cannot_be_marked_retryable_failure(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-OUTCOME-FAILURE")
        claim, _ = self.begin(plane, prepared, lease=60)
        plane.record_provider_dispatch_submission(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
        )
        with self.assertRaisesRegex(RuntimeError, "outcome reconciliation"):
            plane.record_provider_dispatch_attempt_failure(
                prepared["dispatch_id"], claim_token=claim["claim_token"],
                error_class="TRANSPORT_RESPONSE_LOST", retryable=True, now=shift(3)
            )

    def test_no_effect_reconciliation_releases_higher_epoch_retry(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-OUTCOME-NONE")
        adapter = ReconciliationConformantMockProviderAdapter("reference_provider")
        claim, envelope = self.begin(plane, prepared)
        plane.record_provider_dispatch_submission(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
        )
        with self.assertRaisesRegex(RuntimeError, "reconciliation required"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(6)
            )
        evidence = adapter.reconcile(envelope, outcome=OUTCOME_NO_EFFECT)
        resolved = plane.resolve_provider_dispatch_outcome(
            prepared["dispatch_id"], evidence, now=shift(7)
        )
        self.assertEqual(resolved["outcome"], OUTCOME_NO_EFFECT)
        second = plane.claim_provider_dispatch(
            prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(8)
        )
        started = plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"], claim_token=second["claim_token"], now=shift(9)
        )
        self.assertEqual(started["fencing_epoch"], 2)

    def test_completed_reconciliation_admits_lost_receipt_and_survives_restart(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-OUTCOME-DONE")
        adapter = ReconciliationConformantMockProviderAdapter("reference_provider")
        claim, envelope = self.begin(plane, prepared)
        plane.record_provider_dispatch_submission(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
        )
        receipt = adapter.execute(envelope)
        with self.assertRaisesRegex(RuntimeError, "reconciliation required"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(6)
            )
        evidence = adapter.reconcile(envelope, outcome=OUTCOME_COMPLETED)
        resolved = plane.resolve_provider_dispatch_outcome(
            prepared["dispatch_id"], evidence, now=shift(7)
        )
        self.assertEqual(resolved["dispatch"]["provider_receipt"], receipt)
        restarted = OutcomeReconciledProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        readback = restarted.provider_dispatch_outcome_readback()
        self.assertEqual(readback["resolved_completed"], 1)
        self.assertEqual(readback["unresolved_outcomes"], 0)
        self.assertFalse(readback["provider_native_reconciliation_proven"])

    def test_reconciliation_tamper_fails_closed(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-OUTCOME-TAMPER")
        adapter = ReconciliationConformantMockProviderAdapter("reference_provider")
        claim, envelope = self.begin(plane, prepared)
        plane.record_provider_dispatch_submission(
            prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
        )
        with self.assertRaisesRegex(RuntimeError, "reconciliation required"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"], worker_id="worker-b", lease_seconds=60, now=shift(6)
            )
        evidence = adapter.reconcile(envelope, outcome=OUTCOME_NO_EFFECT)
        evidence["fencing_epoch"] = 99
        with self.assertRaisesRegex(RuntimeError, "evidence hash invalid"):
            plane.resolve_provider_dispatch_outcome(
                prepared["dispatch_id"], evidence, now=shift(7)
            )


if __name__ == "__main__":
    unittest.main()
