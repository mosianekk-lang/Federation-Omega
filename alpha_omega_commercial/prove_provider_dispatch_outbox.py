from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from authority_snapshot import digest
from provider_dispatch_outbox import (
    ConformantMockProviderAdapter,
    ProviderDispatchOutboxCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def build_plane(root: Path):
    value = snapshot(1, -20)
    quote_id = "QUOTE-DISPATCH-PROOF"
    bootstrap = ProviderDispatchOutboxCommercialControlPlane(
        root,
        authority_snapshot=value,
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    bootstrap.create_lead("LEAD-DISPATCH-PROOF", "org", "inbound", "delay")
    bootstrap.create_quote_draft(
        quote_id,
        "LEAD-DISPATCH-PROOF",
        "AO-PILOT",
        "ZAR",
        560000.0,
        12,
    )
    subject = bootstrap.quote_authority_subject(quote_id)
    owner = owner_receipt(
        "OWNER-DISPATCH-PROOF",
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        content_sha256=subject["content_sha256"],
    )
    plane = ProviderDispatchOutboxCommercialControlPlane(
        root,
        authority_snapshot=value,
        owner_receipts={owner.receipt_id: owner},
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    plane.approve_quote(
        quote_id,
        owner_decision_receipt_id=owner.receipt_id,
        now=NOW,
    )
    return plane, owner, value, quote_id


def prove(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        plane, owner, value, quote_id = build_plane(root)
        command = {"object_id": quote_id, "mode": "conformance-only"}
        prepared = plane.prepare_provider_dispatch(
            action="quote_approval",
            object_id=quote_id,
            provider_domain="reference_provider",
            operation="dry_run_provider_contract",
            payload=command,
            now=NOW,
        )
        prepared_retry = plane.prepare_provider_dispatch(
            action="quote_approval",
            object_id=quote_id,
            provider_domain="reference_provider",
            operation="dry_run_provider_contract",
            payload=command,
            now=NOW,
        )
        conflicting_command_rejected = False
        try:
            plane.prepare_provider_dispatch(
                action="quote_approval",
                object_id=quote_id,
                provider_domain="reference_provider",
                operation="dry_run_provider_contract",
                payload={"object_id": quote_id, "mode": "changed-command"},
                now=NOW,
            )
        except ValueError as exc:
            conflicting_command_rejected = "provider dispatch conflict" in str(exc)
        adapter = ConformantMockProviderAdapter("reference_provider")
        provider_receipt = adapter.execute(prepared)
        provider_retry = adapter.execute(prepared)
        admitted = plane.admit_provider_dispatch_receipt(
            prepared["dispatch_id"], provider_receipt
        )
        admitted_retry = plane.admit_provider_dispatch_receipt(
            prepared["dispatch_id"], provider_receipt
        )
        restarted = ProviderDispatchOutboxCommercialControlPlane(
            root,
            authority_snapshot=value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        restarted_receipt = restarted.admit_provider_dispatch_receipt(
            prepared["dispatch_id"], provider_receipt
        )
        dispatch_readback = restarted.provider_dispatch_readback()
        authority_readback = restarted.governed_authority_readback()

    checks = {
        "canonical_v11_class": authority_readback["canonical_class"]
        == "ProviderDispatchOutboxCommercialControlPlane",
        "prepared_dispatch_is_idempotent": prepared == prepared_retry,
        "provider_idempotency_key_is_stable": len(
            prepared["provider_idempotency_key"]
        )
        == 64,
        "conflicting_provider_command_is_rejected": conflicting_command_rejected,
        "mock_provider_exact_retry_is_idempotent": provider_receipt
        == provider_retry,
        "receipt_admission_is_idempotent": admitted == admitted_retry,
        "receipt_admission_survives_restart": admitted == restarted_receipt,
        "dispatch_integrity_verified": dispatch_readback["integrity"]
        == "VERIFIED",
        "mock_conformance_receipt_counted": dispatch_readback[
            "mock_conformance_receipts"
        ]
        == 1,
        "live_provider_receipt_not_claimed": dispatch_readback[
            "live_provider_receipts"
        ]
        == 0,
        "verified_live_revenue_remains_zero": authority_readback["revenue"][
            "live_verified_revenue_events"
        ]
        == 0,
    }
    receipt = {
        "control_id": "AO-COMMERCIAL-PROVIDER-DISPATCH-OUTBOX-V11",
        "status": (
            "PROVIDER_DISPATCH_OUTBOX_PROVIDER_PROOF_VERIFIED_"
            "MOCK_CONFORMANCE_ONLY_EXTERNAL_GATES_UNCHANGED"
        ),
        "stage_scope": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len([value for value in checks.values() if not value]),
        "provider_dispatch_safety": {
            "stable_provider_idempotency_key": True,
            "dispatch_bound_to_committed_v10_action": True,
            "exact_prepare_retry_returns_original_record": True,
            "conflicting_command_rejected": True,
            "mock_provider_contract_conformance_verified": True,
            "mock_receipt_replay_is_idempotent": True,
            "restart_safe": True,
            "live_provider_receipt_admitted": False,
            "external_mutation_performed": False,
            "live_provider_operation_proven": False,
            "distributed_provider_exactly_once_proven": False,
        },
        "commercial_truth": {
            "service_enabled_platform_prioritised": True,
            "self_service_saas_held": True,
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
        "provider_boundaries": {
            "cloud_run": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
            "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "customer_market": "MARKET_PROOF_REQUIRED",
            "partner_market": "MARKET_PROOF_REQUIRED",
            "enterprise_assurance": "UNVERIFIED",
            "production_scale": "PRODUCTION_PROOF_REQUIRED",
            "distributed_provider_exactly_once": "PROVIDER_PROOF_REQUIRED",
        },
        "owner_authority": {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        },
        "external_gate_effect": "UNCHANGED",
    }
    receipt["receipt_sha256"] = digest(receipt)
    if receipt["checks_failed"]:
        raise RuntimeError("provider dispatch outbox proof failed")
    (output / "provider-dispatch-outbox-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    print(json.dumps(prove(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
