from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from authority_snapshot import digest, parse_utc
from provider_dispatch_outcome_reconciliation import OUTCOME_COMPLETED, OUTCOME_NO_EFFECT
from provider_reconciliation_evidence_vault import (
    ChallengeBoundMockProviderAdapter,
    VaultedProviderDispatchCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


class ProviderReconciliationEvidenceVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plane_with_dispatch(self, object_id: str):
        bootstrap = VaultedProviderDispatchCommercialControlPlane(
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
        plane = VaultedProviderDispatchCommercialControlPlane(
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
            operation="dry_run_provider_reconciliation_evidence_contract",
            payload={"object_id": object_id, "mode": "evidence-vault-only"},
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
            ttl_seconds=60,
            now=shift(6),
        )
        return envelope, challenge

    def test_no_effect_evidence_is_published_before_resolution_and_restart_safe(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-VAULT-NONE")
        envelope, challenge = self.quarantine(plane, prepared)
        adapter = ChallengeBoundMockProviderAdapter("reference_provider")
        evidence = adapter.reconcile_with_challenge(
            envelope,
            challenge,
            outcome=OUTCOME_NO_EFFECT,
            observed_at=shift(7),
        )
        resolved = plane.resolve_provider_dispatch_outcome(
            prepared["dispatch_id"],
            evidence,
            now=shift(8),
        )
        package = resolved["evidence_package"]
        path = (
            self.root
            / "provider_reconciliation_evidence"
            / package["path"]
        )
        self.assertTrue(path.is_file())
        self.assertEqual(
            package["reconciliation_sha256"], evidence["reconciliation_sha256"]
        )
        restarted = VaultedProviderDispatchCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        readback = restarted.provider_reconciliation_evidence_readback()
        self.assertEqual(readback["evidence_packages"], 1)
        self.assertEqual(readback["referenced_evidence_packages"], 1)
        self.assertEqual(readback["orphaned_evidence_packages"], 0)
        self.assertFalse(readback["provider_native_reconciliation_proven"])

    def test_completed_evidence_tamper_fails_closed_on_restart(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-VAULT-DONE")
        envelope, challenge = self.quarantine(plane, prepared)
        adapter = ChallengeBoundMockProviderAdapter("reference_provider")
        adapter.execute(envelope)
        evidence = adapter.reconcile_with_challenge(
            envelope,
            challenge,
            outcome=OUTCOME_COMPLETED,
            observed_at=shift(7),
        )
        plane.resolve_provider_dispatch_outcome(
            prepared["dispatch_id"],
            evidence,
            now=shift(8),
        )
        path = (
            self.root
            / "provider_reconciliation_evidence"
            / f"{evidence['reconciliation_sha256']}.json"
        )
        package = json.loads(path.read_text(encoding="utf-8"))
        package["evidence"]["provider_effect_observed"] = False
        path.write_text(json.dumps(package), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "package hash invalid"):
            VaultedProviderDispatchCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                owner_receipts={owner.receipt_id: owner},
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )

    def test_failed_resolution_leaves_a_verified_orphan_that_can_be_pruned(self) -> None:
        plane, _, prepared = self.plane_with_dispatch("QUOTE-VAULT-ORPHAN")
        envelope, challenge = self.quarantine(plane, prepared)
        adapter = ChallengeBoundMockProviderAdapter("reference_provider")
        evidence = adapter.reconcile_with_challenge(
            envelope,
            challenge,
            outcome=OUTCOME_NO_EFFECT,
            observed_at=shift(7),
        )
        altered = dict(evidence)
        altered["dispatch_id"] = "different-dispatch"
        altered.pop("reconciliation_sha256")
        altered["reconciliation_sha256"] = digest(altered)
        with self.assertRaisesRegex(RuntimeError, "does not bind"):
            plane.resolve_provider_dispatch_outcome(
                prepared["dispatch_id"],
                altered,
                now=shift(8),
            )
        readback = plane.provider_reconciliation_evidence_readback()
        self.assertEqual(readback["orphaned_evidence_packages"], 1)
        receipt = plane.prune_orphaned_provider_reconciliation_evidence()
        self.assertEqual(receipt["removed_count"], 1)
        self.assertEqual(
            plane.provider_reconciliation_evidence_readback()[
                "orphaned_evidence_packages"
            ],
            0,
        )

    def test_missing_referenced_evidence_fails_closed(self) -> None:
        plane, owner, prepared = self.plane_with_dispatch("QUOTE-VAULT-MISSING")
        envelope, challenge = self.quarantine(plane, prepared)
        adapter = ChallengeBoundMockProviderAdapter("reference_provider")
        evidence = adapter.reconcile_with_challenge(
            envelope,
            challenge,
            outcome=OUTCOME_NO_EFFECT,
            observed_at=shift(7),
        )
        plane.resolve_provider_dispatch_outcome(
            prepared["dispatch_id"],
            evidence,
            now=shift(8),
        )
        (
            self.root
            / "provider_reconciliation_evidence"
            / f"{evidence['reconciliation_sha256']}.json"
        ).unlink()
        with self.assertRaisesRegex(RuntimeError, "evidence missing"):
            VaultedProviderDispatchCommercialControlPlane(
                self.root,
                authority_snapshot=self.value,
                owner_receipts={owner.receipt_id: owner},
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )


if __name__ == "__main__":
    unittest.main()
