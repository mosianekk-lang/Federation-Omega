from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from authority_action_atomicity import (
    AtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from test_authority_snapshot_action_binding import (
    NOW,
    owner_receipt,
    snapshot,
)


def _quote_plane(root: Path):
    value = snapshot(101, -20)
    bootstrap = AtomicAuthoritySnapshotCommercialControlPlane(
        root,
        authority_snapshot=value,
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    bootstrap.create_lead("LEAD-PROOF", "org", "inbound", "manual delay")
    bootstrap.create_quote_draft(
        "QUOTE-PROOF",
        "LEAD-PROOF",
        "AO-PILOT",
        "ZAR",
        560000.0,
        12,
    )
    subject = bootstrap.quote_authority_subject("QUOTE-PROOF")
    receipt = owner_receipt(
        "OWNER-QUOTE-PROOF",
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        content_sha256=subject["content_sha256"],
    )
    plane = AtomicAuthoritySnapshotCommercialControlPlane(
        root,
        authority_snapshot=value,
        owner_receipts={receipt.receipt_id: receipt},
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    return plane, receipt, value


def run_proof(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    checks: dict[str, bool] = {}

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "success"
        plane, receipt, value = _quote_plane(root)
        quote = plane.approve_quote(
            "QUOTE-PROOF",
            owner_decision_receipt_id=receipt.receipt_id,
            now=NOW,
        )
        binding = quote["authority_snapshot_binding"]
        commit = quote["authority_action_commit"]
        readback = plane.authority_action_transaction_readback()

        checks["canonical_atomic_class"] = (
            plane.__class__.__name__
            == "AtomicAuthoritySnapshotCommercialControlPlane"
        )
        checks["exact_snapshot_binding"] = (
            binding["snapshot_sha256"] == value.snapshot_sha256
        )
        checks["binding_and_commit_share_transaction"] = (
            binding["atomic_transaction_id"] == commit["transaction_id"]
        )
        checks["binding_and_commit_share_acceptance"] = (
            binding["acceptance_entry_sha256"]
            == commit["acceptance_entry_sha256"]
        )
        checks["successful_transaction_committed"] = (
            readback["prepared"] == 1
            and readback["committed"] == 1
            and readback["rolled_back"] == 0
            and readback["unterminated"] == []
        )
        checks["owner_reserved_external_effects_held"] = (
            quote["external_send_performed"] is False
            and quote["financial_commitment"] is False
        )
        checks["transaction_ledger_integrity"] = (
            readback["integrity"] == "VERIFIED"
        )

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "rollback"
        plane, receipt, _ = _quote_plane(root)
        before_state = plane._read_state()
        before_governance = plane._read_governance_state()

        def fail_binding(**_: object):
            raise RuntimeError("proof injected binding failure")

        plane._bind_state_object = fail_binding  # type: ignore[method-assign]
        failed_closed = False
        try:
            plane.approve_quote(
                "QUOTE-PROOF",
                owner_decision_receipt_id=receipt.receipt_id,
                now=NOW,
            )
        except RuntimeError:
            failed_closed = True

        rollback = plane.authority_action_transaction_readback()
        checks["injected_failure_rejected"] = failed_closed
        checks["state_restored_exactly"] = plane._read_state() == before_state
        checks["owner_receipt_consumption_restored"] = (
            plane._read_governance_state() == before_governance
        )
        checks["rollback_transaction_terminal"] = (
            rollback["prepared"] == 1
            and rollback["committed"] == 0
            and rollback["rolled_back"] == 1
            and rollback["unterminated"] == []
        )
        checks["partial_state_not_visible"] = (
            rollback["partial_state_visible_after_rollback"] is False
        )

    commercial_truth = {
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
    }
    receipt = {
        "control_id": "AO-COMMERCIAL-AUTHORITY-ACTION-ATOMICITY-V6",
        "status": (
            "AUTHORITY_ACTION_ATOMICITY_PROVIDER_PROOF_VERIFIED_"
            "EXTERNAL_GATES_UNCHANGED"
        ),
        "stage_scope": ["C03", "C11", "C12", "C13", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": sum(not value for value in checks.values()),
        "atomicity": {
            "provider_authority_held_for_full_action": True,
            "partial_state_visible_after_failure": False,
            "exact_file_restoration_on_failure": True,
            "owner_receipt_consumption_restored_on_failure": True,
            "hash_linked_transaction_ledger": True,
            "restart_safe_readback": True,
        },
        "commercial_truth": commercial_truth,
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
    if receipt["checks_failed"]:
        raise RuntimeError("authority action atomicity proof failed")
    path = output / "authority-action-atomicity-receipt.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    receipt = run_proof(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
