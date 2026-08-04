from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from authority_snapshot import (
    AuthorityDomainLease,
    CommercialAuthoritySnapshot,
    CommercialAuthoritySnapshotValidator,
    build_authority_snapshot,
)
from authority_snapshot_control_plane import (
    AuthoritySnapshotCommercialControlPlane,
)
from governed_commercial_assurance import LIVE_AUTHORITY_CLASS
from owner_authority import OwnerDecisionReceipt


NOW = "2026-08-04T04:00:00Z"
GENERATED = "2026-08-04T03:00:00Z"
EXPIRES = "2026-08-05T03:00:00Z"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lease(domain: str, scope: tuple[str, ...]) -> AuthorityDomainLease:
    return AuthorityDomainLease(
        domain=domain,
        state="FRESH_VERIFIED",
        authority_class=LIVE_AUTHORITY_CLASS,
        provider=f"provider-{domain}",
        locator=f"provider://{domain}/receipt/1",
        observed_at=GENERATED,
        scope=scope,
        evidence_sha256=sha(f"evidence-{domain}"),
        max_age_seconds=86400,
    ).with_hash()


def snapshot(*, expires_at: str = EXPIRES, owner_scope: tuple[str, ...] | None = None) -> CommercialAuthoritySnapshot:
    return build_authority_snapshot(
        snapshot_id="AO-AUTH-SNAPSHOT-TEST-1",
        generated_at=GENERATED,
        expires_at=expires_at,
        source_projection_sha256=sha("provider-authority-projection"),
        source_ledger_head=sha("authority-ledger-head"),
        source_ledger_integrity=True,
        domains=(
            lease(
                "owner_decision",
                owner_scope
                if owner_scope is not None
                else ("owner_identity_verification", "decision_receipt_issue"),
            ),
            lease(
                "payment_provider",
                ("settlement_readback", "receipt_verification"),
            ),
            lease(
                "customer_market",
                ("customer_identity", "outcome_evidence"),
            ),
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
        expires_at="2026-08-05T04:00:00Z",
        provider="provider-owner-decision",
        locator=f"provider-owner://{receipt_id}",
        provider_class="OWNER_PROVIDER_NATIVE",
        nonce=f"nonce-{receipt_id}",
    ).with_hash()


class AuthoritySnapshotContractTests(unittest.TestCase):
    def test_valid_snapshot_requires_exact_scope_and_hashes(self) -> None:
        decision = CommercialAuthoritySnapshotValidator(snapshot()).validate_domain(
            "owner_decision",
            required_scope=("owner_identity_verification", "decision_receipt_issue"),
            now=NOW,
        )
        self.assertTrue(decision.valid)
        self.assertEqual(decision.reasons, ())

    def test_tampered_snapshot_is_rejected(self) -> None:
        value = snapshot().to_dict()
        value["domains"]["owner_decision"]["provider"] = "tampered-provider"
        decision = CommercialAuthoritySnapshotValidator(value).validate_domain(
            "owner_decision",
            required_scope=("owner_identity_verification", "decision_receipt_issue"),
            now=NOW,
        )
        self.assertFalse(decision.valid)
        self.assertIn("SNAPSHOT_HASH_INVALID", decision.reasons)
        self.assertIn("AUTHORITY_DOMAIN_HASH_INVALID", decision.reasons)

    def test_expired_snapshot_is_rejected(self) -> None:
        decision = CommercialAuthoritySnapshotValidator(
            snapshot(expires_at="2026-08-04T03:30:00Z")
        ).validate_domain("owner_decision", now=NOW)
        self.assertFalse(decision.valid)
        self.assertIn("SNAPSHOT_EXPIRED", decision.reasons)

    def test_missing_scope_is_rejected(self) -> None:
        decision = CommercialAuthoritySnapshotValidator(
            snapshot(owner_scope=("owner_identity_verification",))
        ).validate_domain(
            "owner_decision",
            required_scope=("owner_identity_verification", "decision_receipt_issue"),
            now=NOW,
        )
        self.assertFalse(decision.valid)
        self.assertIn(
            "AUTHORITY_SCOPE_MISSING:decision_receipt_issue",
            decision.reasons,
        )


class AuthoritySnapshotControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_raw_live_authority_dictionary_cannot_grant_owner_action(self) -> None:
        raw = {
            "owner_decision": {
                "state": "FRESH_VERIFIED",
                "authority_class": LIVE_AUTHORITY_CLASS,
            }
        }
        plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority=raw,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.create_lead("LEAD-1", "org", "inbound", "manual delay")
        plane.create_quote_draft("QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12)
        subject = plane.quote_authority_subject("QUOTE-1")
        receipt = owner_receipt(
            "OWNER-QUOTE-1",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane.owner_receipts[receipt.receipt_id] = receipt
        plane.owner_validator.receipts[receipt.receipt_id] = receipt
        with self.assertRaisesRegex(PermissionError, "AUTHORITY_SNAPSHOT_REQUIRED"):
            plane.approve_quote(
                "QUOTE-1",
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )

    def test_valid_snapshot_allows_governed_quote_presentation_only(self) -> None:
        bootstrap = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=snapshot(),
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        bootstrap.create_lead("LEAD-1", "org", "inbound", "manual delay")
        bootstrap.create_quote_draft("QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12)
        subject = bootstrap.quote_authority_subject("QUOTE-1")
        receipt = owner_receipt(
            "OWNER-QUOTE-1",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=snapshot(),
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        quote = plane.approve_quote(
            "QUOTE-1",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(quote["status"], "OWNER_APPROVED_FOR_EXTERNAL_PRESENTATION")
        self.assertFalse(quote["external_send_performed"])
        self.assertFalse(quote["financial_commitment"])
        readback = plane.governed_authority_readback()
        self.assertTrue(readback["authority_snapshot"]["snapshot_present"])
        self.assertTrue(
            readback["authority_snapshot"]["domains"]["owner_decision"]["valid"]
        )
        self.assertEqual(readback["revenue"]["live_verified_revenue_events"], 0)

    def test_expired_snapshot_blocks_governed_action(self) -> None:
        expired = snapshot(expires_at="2026-08-04T03:30:00Z")
        plane = AuthoritySnapshotCommercialControlPlane(
            self.root,
            authority_snapshot=expired,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.create_lead("LEAD-1", "org", "inbound", "manual delay")
        plane.create_quote_draft("QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12)
        subject = plane.quote_authority_subject("QUOTE-1")
        receipt = owner_receipt(
            "OWNER-QUOTE-1",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane.owner_receipts[receipt.receipt_id] = receipt
        plane.owner_validator.receipts[receipt.receipt_id] = receipt
        with self.assertRaisesRegex(PermissionError, "SNAPSHOT_EXPIRED"):
            plane.approve_quote(
                "QUOTE-1",
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
