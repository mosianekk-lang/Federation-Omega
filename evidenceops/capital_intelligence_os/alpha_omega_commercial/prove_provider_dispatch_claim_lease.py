from __future__ import annotations

import argparse
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from authority_snapshot import digest, parse_utc
from provider_dispatch_claim_lease import (
    LeasedProviderDispatchOutboxCommercialControlPlane,
)
from provider_dispatch_outbox import ConformantMockProviderAdapter
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


def build_plane(root: Path):
    value = snapshot(1, -20)
    quote_id = "QUOTE-DISPATCH-LEASE-PROOF"
    bootstrap = LeasedProviderDispatchOutboxCommercialControlPlane(
        root,
        authority_snapshot=value,
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    bootstrap.create_lead("LEAD-DISPATCH-LEASE-PROOF", "org", "inbound", "delay")
    bootstrap.create_quote_draft(
        quote_id,
        "LEAD-DISPATCH-LEASE-PROOF",
        "AO-PILOT",
        "ZAR",
        560000.0,
        12,
    )
    subject = bootstrap.quote_authority_subject(quote_id)
    owner = owner_receipt(
        "OWNER-DISPATCH-LEASE-PROOF",
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        content_sha256=subject["content_sha256"],
    )
    plane = LeasedProviderDispatchOutboxCommercialControlPlane(
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
    prepared = plane.prepare_provider_dispatch(
        action="quote_approval",
        object_id=quote_id,
        provider_domain="reference_provider",
        operation="dry_run_provider_contract",
        payload={"object_id": quote_id, "mode": "conformance-only"},
        now=NOW,
    )
    return plane, owner, value, prepared


def prove(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        plane, owner, value, prepared = build_plane(root)
        dispatch_id = prepared["dispatch_id"]

        first = plane.claim_provider_dispatch(
            dispatch_id,
            worker_id="worker-a",
            lease_seconds=5,
            now=NOW,
        )
        first_retry = plane.claim_provider_dispatch(
            dispatch_id,
            worker_id="worker-a",
            lease_seconds=5,
            now=shift(1),
        )

        competing_worker_blocked = False
        try:
            plane.claim_provider_dispatch(
                dispatch_id,
                worker_id="worker-b",
                lease_seconds=60,
                now=shift(2),
            )
        except RuntimeError as exc:
            competing_worker_blocked = "another worker" in str(exc)

        takeover = plane.claim_provider_dispatch(
            dispatch_id,
            worker_id="worker-b",
            lease_seconds=60,
            now=shift(6),
        )
        receipt = ConformantMockProviderAdapter("reference_provider").execute(prepared)

        stale_claim_rejected = False
        try:
            plane.admit_provider_dispatch_receipt(
                dispatch_id,
                receipt,
                claim_token=first["claim_token"],
                now=shift(7),
            )
        except RuntimeError as exc:
            stale_claim_rejected = "not current" in str(exc)

        admitted = plane.admit_provider_dispatch_receipt(
            dispatch_id,
            receipt,
            claim_token=takeover["claim_token"],
            now=shift(7),
        )
        restarted = LeasedProviderDispatchOutboxCommercialControlPlane(
            root,
            authority_snapshot=value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        restarted_admission = restarted.admit_provider_dispatch_receipt(
            dispatch_id,
            receipt,
            claim_token=takeover["claim_token"],
            now=shift(8),
        )
        claim_readback = restarted.provider_dispatch_claim_readback()
        dispatch_readback = restarted.provider_dispatch_readback()
        authority_readback = restarted.governed_authority_readback()

    checks = {
        "canonical_v12_class": authority_readback["canonical_class"]
        == "LeasedProviderDispatchOutboxCommercialControlPlane",
        "same_worker_claim_retry_is_idempotent": first == first_retry,
        "competing_worker_is_blocked_during_active_lease": competing_worker_blocked,
        "expired_lease_takeover_increments_attempt": takeover["attempt"] == 2,
        "expired_lease_takeover_changes_token": first["claim_token"]
        != takeover["claim_token"],
        "stale_claim_token_is_rejected": stale_claim_rejected,
        "claimed_receipt_admission_survives_restart": admitted
        == restarted_admission,
        "claim_history_integrity_verified": claim_readback["integrity"]
        == "VERIFIED",
        "one_completed_claim_recorded": claim_readback["completed_claims"] == 1,
        "one_expired_claim_recorded": claim_readback["expired_claims"] == 1,
        "no_active_claim_after_completion": claim_readback["active_claims"] == 0,
        "live_provider_and_revenue_truth_preserved": dispatch_readback[
            "live_provider_receipts"
        ]
        == 0
        and authority_readback["revenue"]["live_verified_revenue_events"] == 0,
    }
    receipt = {
        "control_id": "AO-COMMERCIAL-PROVIDER-DISPATCH-LEASE-V12",
        "status": (
            "PROVIDER_DISPATCH_LOCAL_LEASE_VERIFIED_"
            "LIVE_PROVIDER_PROOF_REQUIRED_EXTERNAL_GATES_UNCHANGED"
        ),
        "stage_scope": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len([value for value in checks.values() if not value]),
        "provider_dispatch_claim_safety": {
            "prepared_v11_dispatch_required": True,
            "one_active_local_worker_per_dispatch": True,
            "same_worker_claim_retry_is_idempotent": True,
            "competing_worker_blocked_during_active_lease": True,
            "bounded_lease_required": True,
            "expired_claim_takeover_supported": True,
            "stale_claim_token_rejected": True,
            "receipt_requires_current_unexpired_claim": True,
            "hash_chained_claim_history": True,
            "local_duplicate_dispatch_prevented": True,
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
        raise RuntimeError("provider dispatch claim lease proof failed")
    (output / "provider-dispatch-claim-lease-receipt.json").write_text(
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
