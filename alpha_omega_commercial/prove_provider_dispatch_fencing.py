from __future__ import annotations

import argparse
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from authority_snapshot import digest, parse_utc
from provider_dispatch_fencing import (
    FencedConformantMockProviderAdapter,
    FencedProviderDispatchCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


def build_plane(root: Path):
    value = snapshot(1, -20)
    quote_id = "QUOTE-DISPATCH-FENCING-PROOF"
    bootstrap = FencedProviderDispatchCommercialControlPlane(
        root,
        authority_snapshot=value,
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    bootstrap.create_lead("LEAD-DISPATCH-FENCING-PROOF", "org", "inbound", "delay")
    bootstrap.create_quote_draft(
        quote_id,
        "LEAD-DISPATCH-FENCING-PROOF",
        "AO-PILOT",
        "ZAR",
        560000.0,
        12,
    )
    subject = bootstrap.quote_authority_subject(quote_id)
    owner = owner_receipt(
        "OWNER-DISPATCH-FENCING-PROOF",
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        content_sha256=subject["content_sha256"],
    )
    plane = FencedProviderDispatchCommercialControlPlane(
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
        operation="dry_run_provider_fencing_contract",
        payload={"object_id": quote_id, "mode": "fencing-conformance-only"},
        now=NOW,
    )
    return plane, owner, value, prepared


def prove(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        plane, owner, value, prepared = build_plane(root)
        dispatch_id = prepared["dispatch_id"]
        adapter = FencedConformantMockProviderAdapter("reference_provider")

        first = plane.claim_provider_dispatch(
            dispatch_id, worker_id="worker-a", lease_seconds=5, now=NOW
        )
        renewed = plane.renew_provider_dispatch_claim(
            dispatch_id,
            claim_token=first["claim_token"],
            lease_seconds=10,
            now=shift(4),
        )
        original_expiry_takeover_blocked = False
        try:
            plane.claim_provider_dispatch(
                dispatch_id, worker_id="worker-b", lease_seconds=60, now=shift(6)
            )
        except RuntimeError as exc:
            original_expiry_takeover_blocked = "another worker" in str(exc)

        first_started = plane.start_provider_dispatch_attempt(
            dispatch_id, claim_token=first["claim_token"], now=shift(7)
        )
        first_started_retry = plane.start_provider_dispatch_attempt(
            dispatch_id, claim_token=first["claim_token"], now=shift(8)
        )
        first_envelope = plane.provider_dispatch_attempt_envelope(
            dispatch_id, claim_token=first["claim_token"], now=shift(8)
        )
        first_receipt = adapter.execute(first_envelope)

        takeover = plane.claim_provider_dispatch(
            dispatch_id, worker_id="worker-b", lease_seconds=60, now=shift(15)
        )
        second_started = plane.start_provider_dispatch_attempt(
            dispatch_id, claim_token=takeover["claim_token"], now=shift(16)
        )
        stale_receipt_rejected = False
        try:
            plane.admit_provider_dispatch_receipt(
                dispatch_id,
                first_receipt,
                claim_token=takeover["claim_token"],
                now=shift(17),
            )
        except RuntimeError as exc:
            stale_receipt_rejected = "current fenced attempt" in str(exc)
        second_envelope = plane.provider_dispatch_attempt_envelope(
            dispatch_id, claim_token=takeover["claim_token"], now=shift(17)
        )
        second_receipt = adapter.execute(second_envelope)
        admitted = plane.admit_provider_dispatch_receipt(
            dispatch_id,
            second_receipt,
            claim_token=takeover["claim_token"],
            now=shift(18),
        )
        restarted = FencedProviderDispatchCommercialControlPlane(
            root,
            authority_snapshot=value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        restarted_admission = restarted.admit_provider_dispatch_receipt(
            dispatch_id,
            second_receipt,
            claim_token=takeover["claim_token"],
            now=shift(19),
        )
        fencing_readback = restarted.provider_dispatch_attempt_readback()
        authority_readback = restarted.governed_authority_readback()

    checks = {
        "canonical_v13_class": authority_readback["canonical_class"]
        == "FencedProviderDispatchCommercialControlPlane",
        "lease_renewal_extends_expiry": renewed["lease_expires_at"] == shift(14),
        "renewal_blocks_takeover_at_original_expiry": original_expiry_takeover_blocked,
        "attempt_start_retry_is_idempotent": first_started == first_started_retry,
        "first_fencing_epoch_is_one": first_started["fencing_epoch"] == 1,
        "takeover_fencing_epoch_is_two": second_started["fencing_epoch"] == 2,
        "stale_attempt_receipt_is_rejected": stale_receipt_rejected,
        "current_fenced_receipt_is_admitted": admitted["provider_receipt"]
        == second_receipt,
        "completion_binding_survives_restart": admitted == restarted_admission,
        "fencing_integrity_verified": fencing_readback["integrity"] == "VERIFIED",
        "one_renewal_and_two_starts_recorded": fencing_readback["renewal_events"]
        == 1
        and fencing_readback["started_attempts"] == 2,
        "provider_and_revenue_truth_preserved": fencing_readback[
            "provider_native_fencing_proven"
        ]
        is False
        and authority_readback["revenue"]["live_verified_revenue_events"] == 0,
    }
    receipt = {
        "control_id": "AO-COMMERCIAL-PROVIDER-DISPATCH-FENCING-V13",
        "status": (
            "PROVIDER_DISPATCH_RENEWAL_AND_FENCING_CONFORMANCE_VERIFIED_"
            "LIVE_PROVIDER_FENCING_PROOF_REQUIRED_EXTERNAL_GATES_UNCHANGED"
        ),
        "stage_scope": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len([value for value in checks.values() if not value]),
        "provider_dispatch_fencing_safety": {
            "prepared_v11_dispatch_required": True,
            "v12_claim_lease_required": True,
            "lease_renewal_supported": True,
            "renewal_must_extend_current_lease": True,
            "one_started_attempt_per_claim": True,
            "monotonic_fencing_epoch_per_claim_attempt": True,
            "attempt_envelope_hash_bound": True,
            "receipt_bound_to_current_fenced_attempt": True,
            "stale_fencing_receipt_rejected": True,
            "terminal_failure_releases_claim": True,
            "mock_provider_fencing_conformance": True,
            "provider_native_fencing_proven": False,
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
            "provider_native_fencing": "PROVIDER_PROOF_REQUIRED",
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
        raise RuntimeError("provider dispatch fencing proof failed")
    (output / "provider-dispatch-fencing-receipt.json").write_text(
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
