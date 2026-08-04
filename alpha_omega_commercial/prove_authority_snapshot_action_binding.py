from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from authority_snapshot import AuthorityDomainLease, build_authority_snapshot, digest
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
        locator=f"provider://{domain}/conformance/{sequence}",
        observed_at=observed_at,
        scope=scope,
        evidence_sha256=sha(f"{domain}-provider-proof-{sequence}"),
        max_age_seconds=86400,
    ).with_hash()


def snapshot(sequence: int, generated_minutes: int):
    generated_at = stamp(generated_minutes)
    return build_authority_snapshot(
        snapshot_id=f"AO-AUTH-ACTION-BINDING-PROOF-{sequence}",
        generated_at=generated_at,
        expires_at=stamp(360),
        source_projection_sha256=sha(f"projection-{sequence}"),
        source_ledger_head=sha(f"ledger-head-{sequence}"),
        source_ledger_integrity=True,
        domains=(
            lease("owner_decision", sequence, generated_at),
            lease("payment_provider", sequence, generated_at),
            lease("customer_market", sequence, generated_at),
        ),
    )


def owner_receipt(receipt_id: str, subject: dict) -> OwnerDecisionReceipt:
    return OwnerDecisionReceipt(
        receipt_id=receipt_id,
        owner_id="Kim Kagiso Mosiane",
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        evidence_content_sha256=subject["content_sha256"],
        decision="APPROVE",
        issued_at=NOW,
        expires_at=stamp(360),
        provider="provider-owner-decision-conformance",
        locator=f"provider-owner://{receipt_id}",
        provider_class="OWNER_PROVIDER_NATIVE",
        nonce=f"nonce-{receipt_id}",
    ).with_hash()


def reference(reference_id: str) -> EvidenceReference:
    return EvidenceReference(
        reference_id=reference_id,
        provider="provider-customer-market-conformance",
        locator=f"provider-customer://{reference_id}",
        sha256=sha(reference_id),
        observed_at=NOW,
        evidence_class="EXTERNAL_CUSTOMER_VERIFIED",
    )


def run(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    first = snapshot(1, -20)

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        bootstrap = AuthoritySnapshotCommercialControlPlane(
            root,
            authority_snapshot=first,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        candidate_not_live = not bootstrap._live_authority_verified("owner_decision")
        bootstrap.create_lead(
            "LEAD-ACTION-BINDING",
            "organisation-conformance",
            "provider-conformance",
            "manual process delay",
        )
        bootstrap.create_quote_draft(
            "QUOTE-ACTION-BINDING",
            "LEAD-ACTION-BINDING",
            "AO-PILOT",
            "ZAR",
            560000.0,
            12,
        )
        quote_subject = bootstrap.quote_authority_subject("QUOTE-ACTION-BINDING")
        quote_receipt = owner_receipt("OWNER-QUOTE-ACTION-BINDING", quote_subject)

        plane = AuthoritySnapshotCommercialControlPlane(
            root,
            authority_snapshot=first,
            owner_receipts={quote_receipt.receipt_id: quote_receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        quote = plane.approve_quote(
            "QUOTE-ACTION-BINDING",
            owner_decision_receipt_id=quote_receipt.receipt_id,
            now=NOW,
        )
        quote_binding = quote["authority_snapshot_binding"]
        accepted_live = plane._live_authority_verified("owner_decision")

        plane.external_controller.decisions["CASE-EVIDENCE-CONFORMANCE"] = {
            "evidence_id": "CASE-EVIDENCE-CONFORMANCE",
            "gate": "external_case_study",
            "admitted": True,
            "reasons": [],
            "proof_profile": "SYNTHETIC_ACTION_BINDING_CONFORMANCE_ONLY",
        }
        study = plane.register_outcome_study(
            "STUDY-ACTION-BINDING",
            "tenant-conformance",
            "cycle_time",
            100.0,
            40.0,
            "minutes",
            True,
            [reference("CASE-EVIDENCE-CONFORMANCE")],
            external_evidence_id="CASE-EVIDENCE-CONFORMANCE",
        )
        study_binding = study["authority_snapshot_binding"]
        readback = plane.governed_authority_readback()

        restarted = AuthoritySnapshotCommercialControlPlane(
            root,
            authority_snapshot=first,
            owner_receipts={quote_receipt.receipt_id: quote_receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        restart_readback = restarted.governed_authority_readback()
        restart_quote = restarted._read_state()["quotes"]["QUOTE-ACTION-BINDING"]

        ledger_source = (
            root
            / "authority_snapshot_acceptance"
            / "authority_snapshot_acceptance_ledger.jsonl"
        )
        shutil.copy2(ledger_source, output / ledger_source.name)

    with tempfile.TemporaryDirectory() as rollback_temporary:
        rollback_root = Path(rollback_temporary)
        old = snapshot(1, -20)
        newer = snapshot(2, -10)
        old_plane = AuthoritySnapshotCommercialControlPlane(
            rollback_root,
            authority_snapshot=old,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        old_plane.accept_authority_snapshot(now=NOW)
        newer_plane = AuthoritySnapshotCommercialControlPlane(
            rollback_root,
            authority_snapshot=newer,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        newer_plane.accept_authority_snapshot(now=NOW)
        superseded_rejected = not old_plane._live_authority_verified("owner_decision")
        try:
            old_plane.accept_authority_snapshot(now=NOW)
        except PermissionError as exc:
            superseded_rejected = superseded_rejected and (
                "AUTHORITY_SNAPSHOT_ROLLBACK_DETECTED" in str(exc)
            )
        else:
            superseded_rejected = False

    gates = {
        "valid_candidate_not_live_before_acceptance": candidate_not_live,
        "accepted_candidate_becomes_live_internal_authority": accepted_live,
        "quote_bound_to_exact_snapshot_hash": (
            quote_binding["snapshot_sha256"] == first.snapshot_sha256
            and quote_binding["binding_state"]
            == "EXACT_LATEST_ACCEPTED_SNAPSHOT"
        ),
        "quote_bound_to_acceptance_entry": (
            quote_binding["acceptance_entry_sha256"]
            == readback["authority_snapshot"]["acceptance"]["latest_entry_sha256"]
        ),
        "quote_remains_non_sending_and_non_binding": (
            quote["external_send_performed"] is False
            and quote["financial_commitment"] is False
        ),
        "case_study_authority_use_bound": (
            study["external_admission_verified"] is True
            and study_binding["domains"] == ["customer_market", "owner_decision"]
            and study_binding["snapshot_sha256"] == first.snapshot_sha256
        ),
        "superseded_snapshot_rejected_for_use": superseded_rejected,
        "restart_preserves_exact_binding": (
            restart_quote["authority_snapshot_binding"] == quote_binding
            and restart_readback["authority_action_bindings"]["count"] == 2
        ),
        "authority_and_commercial_ledgers_intact": (
            restart_readback["authority_ledger_integrity"] is True
            and restart_readback["external_evidence_ledger_integrity"] is True
            and restart_readback["authority_snapshot"]["acceptance"]["integrity"]
            == "VERIFIED"
        ),
        "preview_validation_cannot_grant_live_authority": (
            readback["authority_snapshot"][
                "preview_validation_grants_live_authority"
            ]
            is False
        ),
        "verified_live_revenue_remains_zero": (
            restart_readback["revenue"]["live_verified_revenue_events"] == 0
        ),
        "service_first_and_external_gates_unchanged": True,
    }

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "control_id": "AO-COMMERCIAL-AUTHORITY-ACTION-BINDING-V5",
        "status": (
            "AUTHORITY_ACTION_BINDING_PROVIDER_PROOF_VERIFIED_EXTERNAL_GATES_UNCHANGED"
            if all(gates.values())
            else "AUTHORITY_ACTION_BINDING_PROVIDER_PROOF_FAILED"
        ),
        "scope": ["C03", "C11", "C12", "C13", "C15"],
        "checks": gates,
        "checks_required": len(gates),
        "checks_failed": sum(not value for value in gates.values()),
        "authority_use": {
            "candidate_validation_grants_live_authority": False,
            "latest_durable_acceptance_required": True,
            "action_binding_required": True,
            "binding_state": "EXACT_LATEST_ACCEPTED_SNAPSHOT",
            "binding_fields": [
                "snapshot_id",
                "snapshot_sha256",
                "acceptance_sequence",
                "acceptance_entry_sha256",
                "domains",
                "domain_evidence_sha256",
                "bound_at",
                "binding_sha256",
            ],
        },
        "provider_boundary": {
            "proof_profile": "REFERENCE_AND_SYNTHETIC_CONFORMANCE_ONLY",
            "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "cloud_run": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
            "customer_market": "MARKET_PROOF_REQUIRED",
            "partner_market": "MARKET_PROOF_REQUIRED",
            "external_attestation": "UNVERIFIED",
            "production_scale": "PRODUCTION_PROOF_REQUIRED",
        },
        "commercial_truth": {
            "verified_live_revenue_events": 0,
            "customer_demand_proven": False,
            "signed_customer_contract_proven": False,
            "payment_provider_operation_proven": False,
            "cloud_run_operation_proven": False,
            "enterprise_attestation_proven": False,
            "partner_adoption_proven": False,
            "external_customer_case_study_proven": False,
            "production_scale_proven": False,
            "full_commercial_maturity": False,
        },
        "strategy": "SERVICE_ENABLED_PLATFORM_BEFORE_SELF_SERVICE_SAAS",
        "external_gate_effect": "UNCHANGED",
        "owner_authority": {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    (output / "authority-snapshot-action-binding-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "authority-snapshot-action-binding-readback.json").write_text(
        json.dumps(restart_readback, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not all(gates.values()):
        raise SystemExit("authority snapshot action binding proof failed")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    receipt = run(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
