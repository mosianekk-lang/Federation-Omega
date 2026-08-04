from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from authority_snapshot import digest, parse_utc
from provider_dispatch_outcome_reconciliation import OUTCOME_NO_EFFECT
from provider_reconciliation_recovery import (
    ChallengeBoundMockProviderAdapter,
    RecoverableVaultedProviderDispatchCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


class ProviderReconciliationRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plane_with_dispatch(self, object_id: str):
        bootstrap = RecoverableVaultedProviderDispatchCommercialControlPlane(
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
        plane = RecoverableVaultedProviderDispatchCommercialControlPlane(
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
            operation="dry_run_provider_reconciliation_recovery_contract",
            payload={"object_id": object_id, "mode": "recovery-v17-only"},
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
        evidence = ChallengeBoundMockProviderAdapter(
            "reference_provider"
        ).reconcile_with_challenge(
            envelope,
            challenge,
            outcome=OUTCOME_NO_EFFECT,
            observed_at=shift(7),
        )
        return evidence

    def test_valid_pre_resolution_package_is_protected_and_replayed_after_expiry(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-RECOVERY-VALID")
        evidence = self.quarantine(plane, prepared)

        plane._persist_provider_reconciliation_evidence(evidence)
        restarted = RecoverableVaultedProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        readback = restarted.provider_reconciliation_recovery_readback()
        self.assertEqual(readback["recoverable_evidence_packages"], 1)
        self.assertEqual(readback["invalid_orphaned_evidence_packages"], 0)

        prune = restarted.prune_orphaned_provider_reconciliation_evidence()
        self.assertEqual(prune["removed_count"], 0)
        self.assertEqual(prune["protected_recoverable_count"], 1)

        result = restarted.resume_provider_reconciliation_from_vault(
            evidence["reconciliation_sha256"]
        )
        self.assertEqual(
            result["recovery_receipt"]["reconciliation_sha256"],
            evidence["reconciliation_sha256"],
        )
        self.assertFalse(result["recovery_receipt"]["external_mutation_performed"])
        final = restarted.provider_reconciliation_recovery_readback()
        self.assertEqual(final["referenced_evidence_packages"], 1)
        self.assertEqual(final["recoverable_evidence_packages"], 0)

        retry = restarted.resume_provider_reconciliation_from_vault(
            evidence["reconciliation_sha256"]
        )
        self.assertEqual(retry["status"], "ALREADY_RESOLVED")

    def test_invalid_package_is_not_recoverable_and_can_be_pruned(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-RECOVERY-INVALID")
        evidence = self.quarantine(plane, prepared)
        altered = dict(evidence)
        altered["dispatch_id"] = "different-dispatch"
        altered.pop("reconciliation_sha256")
        altered["reconciliation_sha256"] = digest(altered)
        plane._persist_provider_reconciliation_evidence(altered)

        readback = plane.provider_reconciliation_recovery_readback()
        self.assertEqual(readback["recoverable_evidence_packages"], 0)
        self.assertEqual(readback["invalid_orphaned_evidence_packages"], 1)
        with self.assertRaisesRegex(RuntimeError, "not recoverable"):
            plane.resume_provider_reconciliation_from_vault(
                altered["reconciliation_sha256"]
            )
        prune = plane.prune_orphaned_provider_reconciliation_evidence()
        self.assertEqual(prune["removed_count"], 1)
        self.assertEqual(prune["protected_recoverable_count"], 0)

    def test_recovery_readback_preserves_commercial_truth_boundary(self) -> None:
        plane, _, _ = self.plane_with_dispatch("QUOTE-RECOVERY-BOUNDARY")
        readback = plane.provider_reconciliation_recovery_readback()
        self.assertEqual(
            readback["provider_native_reconciliation_authority"],
            "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        )
        self.assertFalse(readback["provider_native_reconciliation_proven"])
        self.assertFalse(readback["external_mutation_performed"])
        self.assertFalse(readback["live_provider_operation_proven"])


if __name__ == "__main__":
    unittest.main()
