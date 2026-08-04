from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from authority_action_idempotency import (
    IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def build_quote(root: Path, quote_id: str):
    value = snapshot(1, -20)
    bootstrap = IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane(
        root,
        authority_snapshot=value,
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    lead_id = quote_id.replace("QUOTE", "LEAD")
    bootstrap.create_lead(lead_id, "org", "inbound", "manual delay")
    bootstrap.create_quote_draft(
        quote_id,
        lead_id,
        "AO-PILOT",
        "ZAR",
        560000.0,
        12,
    )
    subject = bootstrap.quote_authority_subject(quote_id)
    receipt = owner_receipt(
        "OWNER-" + quote_id,
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        content_sha256=subject["content_sha256"],
    )
    plane = IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane(
        root,
        authority_snapshot=value,
        owner_receipts={receipt.receipt_id: receipt},
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    return plane, receipt, value


def prove(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as exact_tmp:
        exact_root = Path(exact_tmp)
        plane, receipt, value = build_quote(exact_root, "QUOTE-IDEMPOTENCY-PROOF")
        first = plane.approve_quote(
            "QUOTE-IDEMPOTENCY-PROOF",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        first_events = list(plane._transaction_events())
        second = plane.approve_quote(
            "QUOTE-IDEMPOTENCY-PROOF",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        second_events = list(plane._transaction_events())
        restarted = IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane(
            exact_root,
            authority_snapshot=value,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        third = restarted.approve_quote(
            "QUOTE-IDEMPOTENCY-PROOF",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        third_events = list(restarted._transaction_events())
        readback = restarted.authority_action_idempotency_readback()
        authority = restarted.governed_authority_readback()

    with tempfile.TemporaryDirectory() as conflict_tmp:
        conflict_root = Path(conflict_tmp)
        conflict_plane, conflict_receipt, _ = build_quote(
            conflict_root, "QUOTE-IDEMPOTENCY-CONFLICT-PROOF"
        )
        conflict_plane.approve_quote(
            "QUOTE-IDEMPOTENCY-CONFLICT-PROOF",
            owner_decision_receipt_id=conflict_receipt.receipt_id,
            now=NOW,
        )
        state = conflict_plane._read_state()
        state["quotes"]["QUOTE-IDEMPOTENCY-CONFLICT-PROOF"]["amount"] = 1.0
        conflict_plane._write_state(state)
        conflict_rejected = False
        try:
            conflict_plane.approve_quote(
                "QUOTE-IDEMPOTENCY-CONFLICT-PROOF",
                owner_decision_receipt_id=conflict_receipt.receipt_id,
                now=NOW,
            )
        except ValueError as exc:
            conflict_rejected = "idempotency conflict" in str(exc)

    checks = {
        "canonical_idempotent_class": (
            authority["canonical_class"]
            == "IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane"
        ),
        "first_action_committed_once": (
            [event["event"] for event in first_events]
            == ["ACTION_PREPARED", "ACTION_COMMITTED"]
        ),
        "exact_retry_returns_same_record": first == second == third,
        "exact_retry_creates_no_new_transaction": (
            len(first_events) == len(second_events) == len(third_events) == 2
        ),
        "restart_retry_is_safe": third["authority_action_idempotency"]["state"]
        == "EXACT_REPLAY_SAFE",
        "owner_authority_consumed_once": authority["approval_count"] == 1,
        "conflicting_retry_rejected": conflict_rejected,
        "idempotency_integrity_verified": readback["integrity"] == "VERIFIED",
        "idempotency_seal_atomic": readback[
            "idempotency_seal_committed_in_atomic_transaction"
        ],
        "verified_live_revenue_remains_zero": authority["revenue"][
            "live_verified_revenue_events"
        ]
        == 0,
    }

    receipt = {
        "control_id": "AO-COMMERCIAL-AUTHORITY-ACTION-IDEMPOTENCY-V10",
        "status": (
            "AUTHORITY_ACTION_IDEMPOTENCY_PROVIDER_PROOF_VERIFIED_"
            "EXTERNAL_GATES_UNCHANGED"
        ),
        "stage_scope": ["C03", "C11", "C12", "C13", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len([value for value in checks.values() if not value]),
        "idempotency_safety": {
            "exact_retry_returns_committed_record": True,
            "retry_consumes_owner_authority_again": False,
            "conflicting_object_identity_reuse_rejected": True,
            "idempotency_seal_committed_in_atomic_transaction": True,
            "restart_safe": True,
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
        "owner_authority": {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        },
        "provider_boundaries": {
            "cloud_run": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
            "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "customer_market": "MARKET_PROOF_REQUIRED",
            "partner_market": "MARKET_PROOF_REQUIRED",
            "production_scale": "PRODUCTION_PROOF_REQUIRED",
            "distributed_provider_exactly_once": "PROVIDER_PROOF_REQUIRED",
        },
        "external_gate_effect": "UNCHANGED",
    }
    receipt["receipt_sha256"] = digest(receipt)
    if receipt["checks_failed"]:
        raise RuntimeError("authority action idempotency proof failed")
    (output / "authority-action-idempotency-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    receipt = prove(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
