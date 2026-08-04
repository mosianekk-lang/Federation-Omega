from __future__ import annotations

import argparse
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from authority_snapshot import digest, parse_utc
from provider_dispatch_outcome_reconciliation import (
    OUTCOME_COMPLETED,
    OUTCOME_NO_EFFECT,
    OutcomeReconciledProviderDispatchCommercialControlPlane,
    ReconciliationConformantMockProviderAdapter,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


def build_plane(root: Path, quote_id: str):
    value = snapshot(1, -20)
    bootstrap = OutcomeReconciledProviderDispatchCommercialControlPlane(
        root,
        authority_snapshot=value,
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    lead_id = quote_id.replace("QUOTE", "LEAD")
    bootstrap.create_lead(lead_id, "org", "inbound", "delay")
    bootstrap.create_quote_draft(
        quote_id, lead_id, "AO-PILOT", "ZAR", 560000.0, 12
    )
    subject = bootstrap.quote_authority_subject(quote_id)
    owner = owner_receipt(
        "OWNER-" + quote_id,
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        content_sha256=subject["content_sha256"],
    )
    plane = OutcomeReconciledProviderDispatchCommercialControlPlane(
        root,
        authority_snapshot=value,
        owner_receipts={owner.receipt_id: owner},
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    plane.approve_quote(
        quote_id, owner_decision_receipt_id=owner.receipt_id, now=NOW
    )
    prepared = plane.prepare_provider_dispatch(
        action="quote_approval",
        object_id=quote_id,
        provider_domain="reference_provider",
        operation="dry_run_provider_outcome_reconciliation_contract",
        payload={"object_id": quote_id, "mode": "reconciliation-only"},
        now=NOW,
    )
    return plane, owner, value, prepared


def begin(plane, prepared):
    claim = plane.claim_provider_dispatch(
        prepared["dispatch_id"], worker_id="worker-a", lease_seconds=5, now=NOW
    )
    plane.start_provider_dispatch_attempt(
        prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(1)
    )
    envelope = plane.provider_dispatch_attempt_envelope(
        prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(1)
    )
    plane.record_provider_dispatch_submission(
        prepared["dispatch_id"], claim_token=claim["claim_token"], now=shift(2)
    )
    return claim, envelope


def prove(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        adapter = ReconciliationConformantMockProviderAdapter("reference_provider")

        no_effect_plane, _, _, no_effect_dispatch = build_plane(
            root / "no-effect", "QUOTE-OUTCOME-PROOF-NONE"
        )
        _, no_effect_envelope = begin(no_effect_plane, no_effect_dispatch)
        quarantine_created = False
        try:
            no_effect_plane.claim_provider_dispatch(
                no_effect_dispatch["dispatch_id"],
                worker_id="worker-b",
                lease_seconds=60,
                now=shift(6),
            )
        except RuntimeError as exc:
            quarantine_created = "reconciliation required" in str(exc)
        second_takeover_blocked = False
        try:
            no_effect_plane.claim_provider_dispatch(
                no_effect_dispatch["dispatch_id"],
                worker_id="worker-c",
                lease_seconds=60,
                now=shift(7),
            )
        except RuntimeError as exc:
            second_takeover_blocked = "reconciliation required" in str(exc)
        no_effect_evidence = adapter.reconcile(
            no_effect_envelope, outcome=OUTCOME_NO_EFFECT
        )
        no_effect_resolution = no_effect_plane.resolve_provider_dispatch_outcome(
            no_effect_dispatch["dispatch_id"], no_effect_evidence, now=shift(8)
        )
        retry_claim = no_effect_plane.claim_provider_dispatch(
            no_effect_dispatch["dispatch_id"],
            worker_id="worker-b",
            lease_seconds=60,
            now=shift(9),
        )
        retry_start = no_effect_plane.start_provider_dispatch_attempt(
            no_effect_dispatch["dispatch_id"],
            claim_token=retry_claim["claim_token"],
            now=shift(10),
        )

        completed_plane, owner, value, completed_dispatch = build_plane(
            root / "completed", "QUOTE-OUTCOME-PROOF-DONE"
        )
        _, completed_envelope = begin(completed_plane, completed_dispatch)
        lost_receipt = adapter.execute(completed_envelope)
        try:
            completed_plane.claim_provider_dispatch(
                completed_dispatch["dispatch_id"],
                worker_id="worker-b",
                lease_seconds=60,
                now=shift(6),
            )
        except RuntimeError:
            pass
        completed_evidence = adapter.reconcile(
            completed_envelope, outcome=OUTCOME_COMPLETED
        )
        completed_resolution = completed_plane.resolve_provider_dispatch_outcome(
            completed_dispatch["dispatch_id"], completed_evidence, now=shift(8)
        )
        restarted = OutcomeReconciledProviderDispatchCommercialControlPlane(
            root / "completed",
            authority_snapshot=value,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        readback = restarted.provider_dispatch_outcome_readback()
        authority = restarted.governed_authority_readback()

    checks = {
        "canonical_v14_class": authority["canonical_class"]
        == "OutcomeReconciledProviderDispatchCommercialControlPlane",
        "submitted_expiry_creates_quarantine": quarantine_created,
        "unresolved_quarantine_blocks_takeover": second_takeover_blocked,
        "no_effect_resolution_is_hash_bound": no_effect_resolution["outcome"]
        == OUTCOME_NO_EFFECT,
        "no_effect_resolution_allows_retry": retry_claim["attempt"] == 2,
        "retry_uses_higher_fencing_epoch": retry_start["fencing_epoch"] == 2,
        "completed_lookup_recovers_original_receipt": completed_resolution[
            "dispatch"
        ]["provider_receipt"]
        == lost_receipt,
        "completed_resolution_survives_restart": readback["resolved_completed"]
        == 1
        and readback["unresolved_outcomes"] == 0,
        "outcome_integrity_verified": readback["integrity"] == "VERIFIED",
        "submission_and_reconciliation_controls_reported": readback[
            "submission_boundary_is_durable"
        ]
        and readback["unresolved_outcome_blocks_takeover"]
        and readback["completed_resolution_admits_original_receipt"],
        "provider_native_reconciliation_not_claimed": readback[
            "provider_native_reconciliation_proven"
        ]
        is False,
        "provider_and_revenue_truth_preserved": readback[
            "live_provider_operation_proven"
        ]
        is False
        and authority["revenue"]["live_verified_revenue_events"] == 0,
    }
    receipt = {
        "control_id": (
            "AO-COMMERCIAL-PROVIDER-DISPATCH-OUTCOME-RECONCILIATION-V14"
        ),
        "status": (
            "PROVIDER_DISPATCH_UNKNOWN_OUTCOME_QUARANTINE_AND_MOCK_"
            "RECONCILIATION_VERIFIED_LIVE_PROVIDER_PROOF_REQUIRED"
        ),
        "stage_scope": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": sum(not value for value in checks.values()),
        "operational_slice": {
            "durable_submission_marker": True,
            "expired_submitted_attempt_quarantined": True,
            "unresolved_outcome_blocks_retry": True,
            "mock_no_effect_lookup_releases_retry": True,
            "mock_completed_lookup_admits_original_receipt": True,
            "restart_safe_reconciliation": True,
            "provider_native_reconciliation_proven": False,
            "external_mutation_performed": False,
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
            "cloud_run": (
                "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
            ),
            "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "customer_market": "MARKET_PROOF_REQUIRED",
            "partner_market": "MARKET_PROOF_REQUIRED",
            "enterprise_assurance": "UNVERIFIED",
            "production_scale": "PRODUCTION_PROOF_REQUIRED",
            "provider_native_reconciliation": "PROVIDER_PROOF_REQUIRED",
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
        raise RuntimeError("provider dispatch outcome reconciliation proof failed")
    (output / "provider-dispatch-outcome-reconciliation-receipt.json").write_text(
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
