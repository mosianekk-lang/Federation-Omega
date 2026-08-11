from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from commercial_assurance import EvidenceReference
from external_evidence import EvidenceEnvelope
from governed_commercial_assurance import (
    GovernedCommercialAssuranceControlPlane,
    MOCK_AUTHORITY_CLASS,
)
from owner_authority import OwnerDecisionReceipt


NOW = "2026-08-04T02:00:00Z"
EXPIRES = "2026-08-05T02:00:00Z"


def reference(reference_id: str, evidence_class: str = "REFERENCE_PROVIDER") -> EvidenceReference:
    return EvidenceReference(
        reference_id=reference_id,
        provider="github-actions-reference",
        locator=f"artifact://{reference_id}",
        sha256=hashlib.sha256(reference_id.encode("utf-8")).hexdigest(),
        observed_at=NOW,
        evidence_class=evidence_class,
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
        expires_at=EXPIRES,
        provider="mock-owner-decision-provider",
        locator=f"mock-owner://{receipt_id}",
        provider_class="OWNER_PROVIDER_NATIVE",
        nonce=f"nonce-{receipt_id}",
    ).with_hash()


def authority(
    *,
    owner_state: str = "FRESH_VERIFIED",
    payment_state: str = "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    authority_class: str = MOCK_AUTHORITY_CLASS,
) -> dict[str, dict[str, str]]:
    return {
        "owner_decision": {
            "state": owner_state,
            "authority_class": authority_class,
        },
        "payment_provider": {
            "state": payment_state,
            "authority_class": authority_class,
        },
        "customer_market": {
            "state": "MARKET_PROOF_REQUIRED",
            "authority_class": authority_class,
        },
    }


class GovernedCommercialAssuranceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_canonical_signatures_remove_caller_set_approval_shortcuts(self) -> None:
        signatures = GovernedCommercialAssuranceControlPlane.canonical_public_signatures()
        rendered = "\n".join(signatures.values())
        self.assertNotIn("owner_confirmed", rendered)
        self.assertNotIn("owner_approved", rendered)
        self.assertNotIn("owner_approval_reference", rendered)

    def test_owner_reserved_service_request_requires_exact_receipt(self) -> None:
        plane = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=authority(),
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        with self.assertRaises(PermissionError):
            plane.submit_service_request(
                "REQ-SUB-1",
                "tenant-001",
                "subscription.change",
                {"offer_id": "AO-DEPARTMENT"},
                "operator-1",
                now=NOW,
            )

    def test_direct_external_case_study_label_cannot_promote_proof(self) -> None:
        plane = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=authority(),
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        study = plane.register_outcome_study(
            "STUDY-1",
            "tenant-001",
            "cycle_time",
            100.0,
            50.0,
            "minutes",
            True,
            [reference("externally-labelled", "EXTERNAL_CUSTOMER_VERIFIED")],
        )
        self.assertEqual(study["status"], "MARKET_PROOF_REQUIRED")
        self.assertFalse(study["external_admission_verified"])
        self.assertFalse(plane.case_study_report("STUDY-1")["publication_allowed"])

    def test_payment_provider_block_is_preserved_even_with_owner_receipt(self) -> None:
        bootstrap = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=authority(),
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        bootstrap.create_lead("LEAD-1", "org-ref", "reference", "manual delay")
        bootstrap.create_quote_draft("QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12)
        quote_subject = bootstrap.quote_authority_subject("QUOTE-1")
        quote_receipt = owner_receipt(
            "OWNER-QUOTE-1",
            gate=quote_subject["gate"],
            evidence_id=quote_subject["evidence_id"],
            content_sha256=quote_subject["content_sha256"],
        )
        payment_hash = hashlib.sha256(b"provider-payment-receipt").hexdigest()
        payment_receipt = owner_receipt(
            "OWNER-PAY-1",
            gate="payment_provider_revenue",
            evidence_id="PAYMENT-EVIDENCE-1",
            content_sha256=payment_hash,
        )
        plane = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=authority(),
            owner_receipts={
                quote_receipt.receipt_id: quote_receipt,
                payment_receipt.receipt_id: payment_receipt,
            },
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        plane.approve_quote(
            "QUOTE-1",
            owner_decision_receipt_id=quote_receipt.receipt_id,
            now=NOW,
        )
        plane.register_contract_draft("CONTRACT-1", "QUOTE-1", "LEGAL_REVIEW_REQUIRED")
        envelope = EvidenceEnvelope(
            evidence_id="PAYMENT-EVIDENCE-1",
            gate="payment_provider_revenue",
            provider="mock-payment-provider",
            locator="mock-payment://receipt/1",
            observed_at=NOW,
            content_sha256=payment_hash,
            evidence_class="EXTERNAL_PROVIDER_NATIVE",
            claims={
                "settled": True,
                "currency": "ZAR",
                "amount": 1000.0,
                "contract_id": "CONTRACT-1",
            },
            owner_decision_receipt_id=payment_receipt.receipt_id,
        )
        with self.assertRaises(PermissionError):
            plane.register_verified_revenue_event(
                "REV-1",
                "CONTRACT-1",
                1000.0,
                "ZAR",
                envelope,
                now=NOW,
            )
        dashboard = plane.governed_revenue_dashboard()
        self.assertEqual(dashboard["live_verified_revenue_events"], 0)
        self.assertEqual(dashboard["mock_provider_conformance_events"], 0)

    def test_mock_provider_conformance_is_operational_but_never_revenue(self) -> None:
        mock_authority = authority(payment_state="FRESH_VERIFIED")
        bootstrap = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=mock_authority,
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        bootstrap.create_lead("LEAD-1", "org-ref", "reference", "manual delay")
        bootstrap.create_quote_draft("QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12)

        service_subject = bootstrap.service_request_authority_subject(
            "REQ-SUB-1",
            "tenant-001",
            "subscription.change",
            {"offer_id": "AO-DEPARTMENT"},
            "operator-1",
        )
        quote_subject = bootstrap.quote_authority_subject("QUOTE-1")
        payment_hash = hashlib.sha256(b"mock-settled-payment").hexdigest()

        service_receipt = owner_receipt(
            "OWNER-SERVICE-1",
            gate=service_subject["gate"],
            evidence_id=service_subject["evidence_id"],
            content_sha256=service_subject["content_sha256"],
        )
        quote_receipt = owner_receipt(
            "OWNER-QUOTE-1",
            gate=quote_subject["gate"],
            evidence_id=quote_subject["evidence_id"],
            content_sha256=quote_subject["content_sha256"],
        )
        payment_receipt = owner_receipt(
            "OWNER-PAY-1",
            gate="payment_provider_revenue",
            evidence_id="PAYMENT-EVIDENCE-1",
            content_sha256=payment_hash,
        )
        receipts = {
            item.receipt_id: item
            for item in (service_receipt, quote_receipt, payment_receipt)
        }
        plane = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=mock_authority,
            owner_receipts=receipts,
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )

        service = plane.submit_service_request(
            "REQ-SUB-1",
            "tenant-001",
            "subscription.change",
            {"offer_id": "AO-DEPARTMENT"},
            "operator-1",
            owner_decision_receipt_id=service_receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(service["status"], "ACCEPTED_REFERENCE_EXECUTION_PENDING")
        self.assertFalse(service["external_effects_allowed"])

        quote = plane.approve_quote(
            "QUOTE-1",
            owner_decision_receipt_id=quote_receipt.receipt_id,
            now=NOW,
        )
        self.assertEqual(quote["status"], "OWNER_APPROVED_FOR_EXTERNAL_PRESENTATION")
        self.assertFalse(quote["external_send_performed"])
        self.assertFalse(quote["financial_commitment"])
        plane.register_contract_draft("CONTRACT-1", "QUOTE-1", "LEGAL_REVIEW_REQUIRED")

        envelope = EvidenceEnvelope(
            evidence_id="PAYMENT-EVIDENCE-1",
            gate="payment_provider_revenue",
            provider="mock-payment-provider",
            locator="mock-payment://receipt/1",
            observed_at=NOW,
            content_sha256=payment_hash,
            evidence_class="EXTERNAL_PROVIDER_NATIVE",
            claims={
                "settled": True,
                "currency": "ZAR",
                "amount": 1000.0,
                "contract_id": "CONTRACT-1",
            },
            owner_decision_receipt_id=payment_receipt.receipt_id,
        )
        event = plane.register_verified_revenue_event(
            "REV-1",
            "CONTRACT-1",
            1000.0,
            "ZAR",
            envelope,
            now=NOW,
        )
        self.assertEqual(event["status"], "MOCK_PAYMENT_PROVIDER_CONFORMANCE_ONLY")
        self.assertFalse(event["live_revenue_recognition"])
        dashboard = plane.governed_revenue_dashboard()
        self.assertEqual(dashboard["live_verified_revenue_events"], 0)
        self.assertEqual(dashboard["live_verified_revenue_by_currency"], {})
        self.assertEqual(dashboard["mock_provider_conformance_events"], 1)

        restarted = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=mock_authority,
            owner_receipts=receipts,
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        readback = restarted.governed_authority_readback()
        self.assertTrue(readback["caller_set_approval_parameters_absent"])
        self.assertTrue(readback["authority_ledger_integrity"])
        self.assertTrue(readback["external_evidence_ledger_integrity"])
        self.assertEqual(len(readback["consumed_owner_receipts"]), 3)
        self.assertEqual(readback["revenue"]["live_verified_revenue_events"], 0)

    def test_owner_receipt_cannot_be_reused_for_different_subject(self) -> None:
        mock_authority = authority()
        bootstrap = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=mock_authority,
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        subject = bootstrap.service_request_authority_subject(
            "REQ-SUB-1",
            "tenant-001",
            "subscription.change",
            {"offer_id": "AO-DEPARTMENT"},
            "operator-1",
        )
        receipt = owner_receipt(
            "OWNER-SERVICE-1",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=mock_authority,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        plane.submit_service_request(
            "REQ-SUB-1",
            "tenant-001",
            "subscription.change",
            {"offer_id": "AO-DEPARTMENT"},
            "operator-1",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        with self.assertRaises(PermissionError):
            plane.submit_service_request(
                "REQ-SUB-2",
                "tenant-001",
                "subscription.change",
                {"offer_id": "AO-ENTERPRISE"},
                "operator-1",
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )

    def test_governance_ledger_tampering_is_detected_on_readback(self) -> None:
        mock_authority = authority()
        bootstrap = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=mock_authority,
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        subject = bootstrap.service_request_authority_subject(
            "REQ-SUB-1",
            "tenant-001",
            "subscription.change",
            {"offer_id": "AO-DEPARTMENT"},
            "operator-1",
        )
        receipt = owner_receipt(
            "OWNER-SERVICE-1",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = GovernedCommercialAssuranceControlPlane(
            self.root,
            authority=mock_authority,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        plane.submit_service_request(
            "REQ-SUB-1",
            "tenant-001",
            "subscription.change",
            {"offer_id": "AO-DEPARTMENT"},
            "operator-1",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        rows = plane.governance_ledger_file.read_text(encoding="utf-8").splitlines()
        event = json.loads(rows[0])
        event["payload"]["gate"] = "tampered"
        plane.governance_ledger_file.write_text(json.dumps(event) + "\n", encoding="utf-8")
        self.assertFalse(plane.verify_governance_ledger())
        with self.assertRaises(RuntimeError):
            GovernedCommercialAssuranceControlPlane(
                self.root,
                authority=mock_authority,
                owner_receipts={receipt.receipt_id: receipt},
                authority_profile="MOCK_PROVIDER_CONFORMANCE",
            )


if __name__ == "__main__":
    unittest.main()
