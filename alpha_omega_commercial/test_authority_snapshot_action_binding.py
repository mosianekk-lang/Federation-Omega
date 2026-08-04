from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from authority_snapshot import AuthorityDomainLease, build_authority_snapshot
from authority_snapshot_control_plane import AuthoritySnapshotCommercialControlPlane
from commercial_assurance import EvidenceReference
from governed_commercial_assurance import LIVE_AUTHORITY_CLASS
from owner_authority import OwnerDecisionReceipt


BASE = datetime.now(timezone.utc).replace(microsecond=0)
NOW = BASE.isoformat().replace("+00:00", "Z")


def stamp(minutes: int) -> str:
    return (BASE + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lease(domain: str, sequence: int, observed_at: str) -> AuthorityDomainLease:
    scope = {
        "owner_decision": ("owner_identity_verification", "decision_receipt_issue"),
        "payment_provider": ("settlement_readback", "receipt_verification"),
        "customer_market": ("customer_identity", "outcome_evidence"),
    }[domain]
    return AuthorityDomainLease(
        domain=domain,
        state="FRESH_VERIFIED",
        authority_class=LIVE_AUTHORITY_CLASS,
        provider=f"provider-{domain}",
        locator=f"provider://{domain}/receipt/{sequence}",
        observed_at=observed_at,
        scope=scope,
        evidence_sha256=sha(f"{domain}-evidence-{sequence}"),
        max_age_seconds=86400,
    ).with_hash()


def snapshot(sequence: int, generated_minutes: int):
    generated_at = stamp(generated_minutes)
    return build_authority_snapshot(
        snapshot_id=f"AO-AUTH-ACTION-BINDING-{sequence}",
        generated_at=generated_at,
        expires_at=stamp(360),
        source_projection_sha256=sha(f"projection-{sequence}"),
        source_ledger_head=sha(f"source-head-{sequence}"),
        source_ledger_integrity=True,
        domains=(
            lease("owner_decision", sequence, generated_at),
            lease("payment_provider", sequence, generated_at),
            lease("customer_market", sequence, generated_at),
        ),
    )


def owner_receipt(
    receipt_id: str,
    *,
    gate: str,
    evidence_id: str,
    content_sha256: str,
) -> OwnerDecisionReceipt:
    return OwnerDecisionReceipt(
        receipt_id=receipt_id,
        owner_id="Kim Kagiso Mosiane",
        gate=gate,
        evidence_id=evidence_id,
        evidence_content_sha256=content_sha256,
        decision="APPROVE",
        issued_at=NOW,
        expires_at=stamp(360),
        provider="provider-owner-decision",
        locator=f"provider-owner://{receipt_id}",
        provider_class="OWNER_PROVIDER_NATIVE",
        nonce=f"nonce-{receipt_id}",
    ).with_hash()


def evidence(reference_id: str) -> EvidenceReference:
    return EvidenceReference(
        reference_id=reference_id,
        provider="provider-customer-market",
        locator=f"provider-customer://{reference_id}",
        sha256=sha(reference_id),
        observed_at=NOW,
        evidence_class="EXTERNAL_CUSTOMER_VERIFIED",
    )


class AuthoritySnapshotActionBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.value = snapshot(1, -20)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_valid_candidate_is_not_live_until_durably_accepted(self) -> None:
        plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        self.assertFalse(plane._live_authority_verified("owner_decision"))
        plane.accept_authority_snapshot(now=NOW)
        self.assertTrue(plane._live_authority_verified("owner_decision"))
        readback = plane.authority_snapshot_readback(now=NOW)
        self.assertTrue(readback["acceptance"]["candidate_latest_accepted"])
        self.assertFalse(readback["preview_validation_grants_live_authority"])

    def test_quote_is_bound_to_exact_latest_acceptance_entry(self) -> None:
        bootstrap = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        bootstrap.create_lead("LEAD-1", "org", "inbound", "manual delay")
        bootstrap.create_quote_draft(
            "QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12
        )
        subject = bootstrap.quote_authority_subject("QUOTE-1")
        receipt = owner_receipt(
            "OWNER-QUOTE-1",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        quote = plane.approve_quote(
            "QUOTE-1",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        binding = quote["authority_snapshot_binding"]
        acceptance = plane.authority_snapshot_readback(now=NOW)["acceptance"]
        self.assertEqual(binding["binding_state"], "EXACT_LATEST_ACCEPTED_SNAPSHOT")
        self.assertEqual(binding["snapshot_sha256"], self.value.snapshot_sha256)
        self.assertEqual(
            binding["acceptance_entry_sha256"], acceptance["latest_entry_sha256"]
        )
        self.assertEqual(binding["domains"], ["owner_decision"])
        self.assertFalse(quote["external_send_performed"])
        self.assertFalse(quote["financial_commitment"])

    def test_external_outcome_promotion_is_bound_before_use(self) -> None:
        plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.external_controller.decisions["CASE-EVIDENCE-1"] = {
            "evidence_id": "CASE-EVIDENCE-1",
            "gate": "external_case_study",
            "admitted": True,
            "reasons": [],
        }
        study = plane.register_outcome_study(
            "STUDY-1",
            "tenant-001",
            "cycle_time",
            100.0,
            40.0,
            "minutes",
            True,
            [evidence("CASE-EVIDENCE-1")],
            external_evidence_id="CASE-EVIDENCE-1",
        )
        self.assertTrue(study["external_admission_verified"])
        binding = study["authority_snapshot_binding"]
        self.assertEqual(
            binding["domains"], ["customer_market", "owner_decision"]
        )
        self.assertEqual(binding["snapshot_sha256"], self.value.snapshot_sha256)
        self.assertEqual(binding["binding_state"], "EXACT_LATEST_ACCEPTED_SNAPSHOT")

    def test_superseded_snapshot_cannot_authorize_or_bind_a_later_action(self) -> None:
        old_plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        old_plane.create_lead("LEAD-1", "org", "inbound", "manual delay")
        old_plane.create_quote_draft(
            "QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12
        )
        subject = old_plane.quote_authority_subject("QUOTE-1")
        receipt = owner_receipt(
            "OWNER-QUOTE-1",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        old_plane.owner_receipts[receipt.receipt_id] = receipt
        old_plane.owner_validator.receipts[receipt.receipt_id] = receipt
        old_plane.accept_authority_snapshot(now=NOW)

        newer_value = snapshot(2, -10)
        newer_plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=newer_value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        newer_plane.accept_authority_snapshot(now=NOW)

        self.assertFalse(old_plane._live_authority_verified("owner_decision"))
        with self.assertRaisesRegex(
            PermissionError, "AUTHORITY_SNAPSHOT_ROLLBACK_DETECTED"
        ):
            old_plane.approve_quote(
                "QUOTE-1",
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )

    def test_restart_preserves_action_binding_and_zero_revenue(self) -> None:
        bootstrap = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        bootstrap.create_lead("LEAD-1", "org", "inbound", "manual delay")
        bootstrap.create_quote_draft(
            "QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12
        )
        subject = bootstrap.quote_authority_subject("QUOTE-1")
        receipt = owner_receipt(
            "OWNER-QUOTE-1",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        original = plane.approve_quote(
            "QUOTE-1",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )["authority_snapshot_binding"]

        restarted = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=self.value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        readback = restarted.governed_authority_readback()
        stored = restarted._read_state()["quotes"]["QUOTE-1"]
        self.assertEqual(stored["authority_snapshot_binding"], original)
        self.assertEqual(readback["authority_action_bindings"]["count"], 1)
        self.assertEqual(readback["revenue"]["live_verified_revenue_events"], 0)
        self.assertTrue(readback["authority_ledger_integrity"])


if __name__ == "__main__":
    unittest.main()
