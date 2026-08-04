from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from authority_snapshot import parse_utc
from provider_dispatch_outcome_reconciliation import OUTCOME_NO_EFFECT
from provider_reconciliation_recovery import (
    RecoverableVaultedProviderDispatchCommercialControlPlane,
)
from provider_reconciliation_recovery_completion import (
    ChallengeBoundMockProviderAdapter,
    ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


class ProviderReconciliationRecoveryCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plane_with_dispatch(self, object_id: str):
        bootstrap = ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane(
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
        plane = ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.approve_quote(
            object_id,
            owner_decision_receipt_id=owner.receipt_id,
            now=NOW,
        )
        prepared = plane.prepare_provider_dispatch(
            action="quote_approval",
            object_id=object_id,
            provider_domain="reference_provider",
            operation="dry_run_provider_reconciliation_recovery_completion_contract",
            payload={"object_id": object_id, "mode": "completion-v18-only"},
            now=NOW,
        )
        return plane, owner, prepared

    def quarantine(self, plane, prepared):
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"],
            worker_id="worker-a",
            lease_seconds=5,
            now=NOW,
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(1),
        )
        envelope = plane.provider_dispatch_attempt_envelope(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(1),
        )
        plane.record_provider_dispatch_submission(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(2),
        )
        with self.assertRaisesRegex(RuntimeError, "reconciliation required"):
            plane.claim_provider_dispatch(
                prepared["dispatch_id"],
                worker_id="worker-b",
                lease_seconds=60,
                now=shift(6),
            )
        challenge = plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"],
            ttl_seconds=10,
            now=shift(6),
        )
        return ChallengeBoundMockProviderAdapter(
            "reference_provider"
        ).reconcile_with_challenge(
            envelope,
            challenge,
            outcome=OUTCOME_NO_EFFECT,
            observed_at=shift(7),
        )

    def test_post_resolution_crash_gap_is_repaired_without_reconciliation_reexecution(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-COMPLETION-REPAIR")
        evidence = self.quarantine(plane, prepared)
        plane._persist_provider_reconciliation_evidence(evidence)

        # Simulate the V17 process committing the resolution and then stopping before
        # the V18 completion receipt can be atomically published.
        RecoverableVaultedProviderDispatchCommercialControlPlane.resume_provider_reconciliation_from_vault(
            plane, evidence["reconciliation_sha256"]
        )
        self.assertFalse(
            plane._completion_receipt_path(
                evidence["reconciliation_sha256"]
            ).exists()
        )

        restarted = ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        repaired = restarted.resume_provider_reconciliation_from_vault(
            evidence["reconciliation_sha256"]
        )
        self.assertEqual(repaired["status"], "ALREADY_RESOLVED")
        self.assertTrue(repaired["completion_receipt_repaired"])
        self.assertFalse(repaired["external_mutation_performed"])
        receipt = repaired["recovery_completion_receipt"]
        self.assertEqual(
            receipt["reconciliation_sha256"], evidence["reconciliation_sha256"]
        )
        self.assertFalse(receipt["external_mutation_performed"])

    def test_exact_retry_returns_the_same_verified_completion_receipt(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-COMPLETION-IDEMPOTENT")
        evidence = self.quarantine(plane, prepared)
        plane._persist_provider_reconciliation_evidence(evidence)
        first = plane.resume_provider_reconciliation_from_vault(
            evidence["reconciliation_sha256"]
        )
        second = plane.resume_provider_reconciliation_from_vault(
            evidence["reconciliation_sha256"]
        )
        self.assertEqual(second["status"], "ALREADY_RESOLVED")
        self.assertFalse(second["completion_receipt_repaired"])
        self.assertEqual(
            first["recovery_completion_receipt"],
            second["recovery_completion_receipt"],
        )

    def test_tampered_completion_receipt_fails_closed_on_restart(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-COMPLETION-TAMPER")
        evidence = self.quarantine(plane, prepared)
        plane._persist_provider_reconciliation_evidence(evidence)
        result = plane.resume_provider_reconciliation_from_vault(
            evidence["reconciliation_sha256"]
        )
        path = plane._completion_receipt_path(evidence["reconciliation_sha256"])
        altered = dict(result["recovery_completion_receipt"])
        altered["resolved_dispatch_record_sha256"] = "0" * 64
        path.write_text(json.dumps(altered), encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "receipt hash invalid"):
            ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                owner_receipts={owner.receipt_id: owner},
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )

    def test_readback_preserves_commercial_truth_boundary(self) -> None:
        plane, _, _ = self.plane_with_dispatch("QUOTE-COMPLETION-BOUNDARY")
        readback = plane.provider_reconciliation_recovery_completion_readback()
        self.assertTrue(readback["atomic_completion_receipt_publication"])
        self.assertTrue(readback["post_resolution_receipt_repair_supported"])
        self.assertFalse(
            readback["reconciliation_reexecution_on_receipt_repair"]
        )
        self.assertEqual(
            readback["provider_native_reconciliation_authority"],
            "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        )
        self.assertFalse(readback["provider_native_reconciliation_proven"])
        self.assertFalse(readback["external_mutation_performed"])
        self.assertFalse(readback["live_provider_operation_proven"])


if __name__ == "__main__":
    unittest.main()
