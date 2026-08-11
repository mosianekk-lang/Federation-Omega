from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from commercial_assurance import EvidenceReference, digest
from external_evidence import EvidenceEnvelope
from governed_commercial_assurance import (
    GovernedCommercialAssuranceControlPlane,
    MOCK_AUTHORITY_CLASS,
)
from owner_authority import OwnerDecisionReceipt


NOW = "2026-08-04T02:00:00Z"
EXPIRES = "2026-08-05T02:00:00Z"


def owner_receipt(receipt_id: str, subject: dict) -> OwnerDecisionReceipt:
    return OwnerDecisionReceipt(
        receipt_id=receipt_id,
        owner_id="Kim Kagiso Mosiane",
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        evidence_content_sha256=subject["content_sha256"],
        decision="APPROVE",
        issued_at=NOW,
        expires_at=EXPIRES,
        provider="mock-owner-decision-provider",
        locator=f"mock-owner://{receipt_id}",
        provider_class="OWNER_PROVIDER_NATIVE",
        nonce=f"nonce-{receipt_id}",
    ).with_hash()


def mock_authority(payment_state: str) -> dict[str, dict[str, str]]:
    return {
        "owner_decision": {
            "state": "FRESH_VERIFIED",
            "authority_class": MOCK_AUTHORITY_CLASS,
        },
        "payment_provider": {
            "state": payment_state,
            "authority_class": MOCK_AUTHORITY_CLASS,
        },
        "customer_market": {
            "state": "MARKET_PROOF_REQUIRED",
            "authority_class": MOCK_AUTHORITY_CLASS,
        },
    }


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as blocked_dir:
        blocked = GovernedCommercialAssuranceControlPlane(
            blocked_dir,
            authority=mock_authority("PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"),
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        blocked_service = False
        try:
            blocked.submit_service_request(
                "REQ-BLOCKED",
                "tenant-001",
                "subscription.change",
                {"offer_id": "AO-DEPARTMENT"},
                "operator-1",
                now=NOW,
            )
        except PermissionError:
            blocked_service = True

        fake_study = blocked.register_outcome_study(
            "STUDY-BLOCKED",
            "tenant-001",
            "cycle_time",
            100.0,
            40.0,
            "minutes",
            True,
            [
                EvidenceReference(
                    reference_id="fake-external",
                    provider="reference-provider",
                    locator="reference://fake",
                    sha256=hashlib.sha256(b"fake").hexdigest(),
                    observed_at=NOW,
                    evidence_class="EXTERNAL_CUSTOMER_VERIFIED",
                )
            ],
        )
        blocked_readback = blocked.governed_authority_readback()

    with tempfile.TemporaryDirectory() as conformance_dir:
        authority = mock_authority("FRESH_VERIFIED")
        bootstrap = GovernedCommercialAssuranceControlPlane(
            conformance_dir,
            authority=authority,
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        bootstrap.create_lead(
            "LEAD-CONFORMANCE",
            "organisation-reference",
            "reference-provider",
            "manual process delay",
        )
        bootstrap.create_quote_draft(
            "QUOTE-CONFORMANCE",
            "LEAD-CONFORMANCE",
            "AO-PILOT",
            "ZAR",
            560000.0,
            12,
        )

        service_subject = bootstrap.service_request_authority_subject(
            "REQ-CONFORMANCE",
            "tenant-001",
            "subscription.change",
            {"offer_id": "AO-DEPARTMENT"},
            "operator-1",
        )
        quote_subject = bootstrap.quote_authority_subject("QUOTE-CONFORMANCE")
        payment_content_sha256 = hashlib.sha256(
            b"mock-provider-settlement-conformance"
        ).hexdigest()
        payment_subject = {
            "gate": "payment_provider_revenue",
            "evidence_id": "PAYMENT-CONFORMANCE",
            "content_sha256": payment_content_sha256,
        }
        receipts = {
            receipt.receipt_id: receipt
            for receipt in (
                owner_receipt("OWNER-SERVICE-CONFORMANCE", service_subject),
                owner_receipt("OWNER-QUOTE-CONFORMANCE", quote_subject),
                owner_receipt("OWNER-PAYMENT-CONFORMANCE", payment_subject),
            )
        }

        plane = GovernedCommercialAssuranceControlPlane(
            conformance_dir,
            authority=authority,
            owner_receipts=receipts,
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        service = plane.submit_service_request(
            "REQ-CONFORMANCE",
            "tenant-001",
            "subscription.change",
            {"offer_id": "AO-DEPARTMENT"},
            "operator-1",
            owner_decision_receipt_id="OWNER-SERVICE-CONFORMANCE",
            now=NOW,
        )
        quote = plane.approve_quote(
            "QUOTE-CONFORMANCE",
            owner_decision_receipt_id="OWNER-QUOTE-CONFORMANCE",
            now=NOW,
        )
        contract = plane.register_contract_draft(
            "CONTRACT-CONFORMANCE",
            "QUOTE-CONFORMANCE",
            "LEGAL_REVIEW_REQUIRED",
        )
        payment = EvidenceEnvelope(
            evidence_id="PAYMENT-CONFORMANCE",
            gate="payment_provider_revenue",
            provider="mock-payment-provider",
            locator="mock-payment://settlement/conformance",
            observed_at=NOW,
            content_sha256=payment_content_sha256,
            evidence_class="EXTERNAL_PROVIDER_NATIVE",
            claims={
                "settled": True,
                "currency": "ZAR",
                "amount": 1000.0,
                "contract_id": "CONTRACT-CONFORMANCE",
            },
            owner_decision_receipt_id="OWNER-PAYMENT-CONFORMANCE",
        )
        revenue = plane.register_verified_revenue_event(
            "REV-CONFORMANCE",
            "CONTRACT-CONFORMANCE",
            1000.0,
            "ZAR",
            payment,
            now=NOW,
        )
        readback = plane.governed_authority_readback()
        restarted = GovernedCommercialAssuranceControlPlane(
            conformance_dir,
            authority=authority,
            owner_receipts=receipts,
            authority_profile="MOCK_PROVIDER_CONFORMANCE",
        )
        restart_readback = restarted.governed_authority_readback()

    signatures = GovernedCommercialAssuranceControlPlane.canonical_public_signatures()
    gates = {
        "legacy_boolean_shortcuts_absent": all(
            forbidden not in signature
            for signature in signatures.values()
            for forbidden in (
                "owner_confirmed",
                "owner_approved",
                "owner_approval_reference",
            )
        ),
        "owner_reserved_service_blocked_without_receipt": blocked_service,
        "direct_external_case_study_label_rejected": (
            fake_study["status"] == "MARKET_PROOF_REQUIRED"
            and not fake_study["external_admission_verified"]
        ),
        "mock_service_authority_conformance": (
            service["status"] == "ACCEPTED_REFERENCE_EXECUTION_PENDING"
            and service["external_effects_allowed"] is False
        ),
        "mock_quote_authority_conformance": (
            quote["status"] == "OWNER_APPROVED_FOR_EXTERNAL_PRESENTATION"
            and quote["external_send_performed"] is False
            and quote["financial_commitment"] is False
        ),
        "contract_remains_draft": (
            contract["status"] == "DRAFT_NOT_EXECUTED"
            and contract["binding"] is False
        ),
        "mock_payment_conformance_not_revenue": (
            revenue["status"] == "MOCK_PAYMENT_PROVIDER_CONFORMANCE_ONLY"
            and revenue["live_revenue_recognition"] is False
            and readback["revenue"]["live_verified_revenue_events"] == 0
            and readback["revenue"]["mock_provider_conformance_events"] == 1
        ),
        "governance_ledger_integrity": readback["authority_ledger_integrity"],
        "external_evidence_ledger_integrity": readback[
            "external_evidence_ledger_integrity"
        ],
        "restart_safe_owner_receipt_consumption": (
            restart_readback["consumed_owner_receipts"]
            == readback["consumed_owner_receipts"]
            and len(restart_readback["consumed_owner_receipts"]) == 3
        ),
        "blocked_surface_live_revenue_zero": (
            blocked_readback["revenue"]["live_verified_revenue_events"] == 0
        ),
    }

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "control_id": "AO-COMMERCIAL-GOVERNED-AUTHORITY-V2",
        "status": (
            "GOVERNED_COMMERCIAL_AUTHORITY_V2_VERIFIED_EXTERNAL_GATES_UNCHANGED"
            if all(gates.values())
            else "GOVERNED_COMMERCIAL_AUTHORITY_V2_FAILED"
        ),
        "scope": ["C11", "C12", "C13", "C15"],
        "gates": gates,
        "canonical_api": {
            "class": "GovernedCommercialAssuranceControlPlane",
            "legacy_class": "CommercialAssuranceControlPlane",
            "legacy_state": "REFERENCE_ONLY_NOT_CANONICAL",
            "public_signatures": signatures,
        },
        "provider_boundary": {
            "proof_profile": "MOCK_PROVIDER_CONFORMANCE",
            "live_payment_provider_authority": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "live_owner_decision_authority": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
            "customer_market": "MARKET_PROOF_REQUIRED",
        },
        "commercial_truth": {
            "live_verified_revenue_events": 0,
            "mock_provider_conformance_events": 1,
            "customer_demand_proven": False,
            "signed_contract_proven": False,
            "payment_proven": False,
            "cloud_run_operation_proven": False,
            "enterprise_attestation_proven": False,
            "partner_adoption_proven": False,
            "external_case_study_proven": False,
            "production_scale_proven": False,
            "full_commercial_maturity": False,
        },
        "owner_authority": {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    (output / "governed-commercial-authority-v2-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "canonical-api-readback.json").write_text(
        json.dumps(restart_readback, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not all(gates.values()):
        raise SystemExit("governed commercial authority proof failed")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
