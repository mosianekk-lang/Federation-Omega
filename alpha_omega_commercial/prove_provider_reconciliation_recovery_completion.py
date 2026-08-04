from __future__ import annotations

import argparse
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any

from authority_snapshot import parse_utc
from provider_dispatch_outcome_reconciliation import OUTCOME_NO_EFFECT
from provider_reconciliation_recovery import (
    RecoverableVaultedProviderDispatchCommercialControlPlane,
)
from provider_reconciliation_recovery_completion import (
    ChallengeBoundMockProviderAdapter,
    ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane,
)
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def shift(seconds: int) -> str:
    return (parse_utc(NOW) + timedelta(seconds=seconds)).isoformat().replace(
        "+00:00", "Z"
    )


def exercise() -> tuple[dict[str, bool], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        authority = snapshot(1, -20)
        bootstrap = ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane(
            root,
            authority_snapshot=authority,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        bootstrap.create_lead("LEAD-V18", "org", "inbound", "delay")
        bootstrap.create_quote_draft(
            "QUOTE-V18", "LEAD-V18", "AO-PILOT", "ZAR", 560000.0, 12
        )
        subject = bootstrap.quote_authority_subject("QUOTE-V18")
        owner = owner_receipt(
            "OWNER-QUOTE-V18",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        plane = ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane(
            root,
            authority_snapshot=authority,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.approve_quote(
            "QUOTE-V18",
            owner_decision_receipt_id=owner.receipt_id,
            now=NOW,
        )
        prepared = plane.prepare_provider_dispatch(
            action="quote_approval",
            object_id="QUOTE-V18",
            provider_domain="reference_provider",
            operation="dry_run_recovery_completion_v18",
            payload={"object_id": "QUOTE-V18", "mode": "v18-proof"},
            now=NOW,
        )
        claim = plane.claim_provider_dispatch(
            prepared["dispatch_id"],
            worker_id="worker-a",
            lease_seconds=5,
            now=NOW,
        )
        plane.start_provider_dispatch_attempt(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(1),
        )
        envelope = plane.provider_dispatch_attempt_envelope(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(1),
        )
        plane.record_provider_dispatch_submission(
            prepared["dispatch_id"],
            claim_token=claim["claim_token"],
            now=shift(2),
        )
        try:
            plane.claim_provider_dispatch(
                prepared["dispatch_id"],
                worker_id="worker-b",
                lease_seconds=60,
                now=shift(6),
            )
        except RuntimeError as exc:
            quarantine_enforced = "reconciliation required" in str(exc)
        else:
            quarantine_enforced = False
        challenge = plane.issue_provider_reconciliation_challenge(
            prepared["dispatch_id"], ttl_seconds=10, now=shift(6)
        )
        evidence = ChallengeBoundMockProviderAdapter(
            "reference_provider"
        ).reconcile_with_challenge(
            envelope,
            challenge,
            outcome=OUTCOME_NO_EFFECT,
            observed_at=shift(7),
        )
        plane._persist_provider_reconciliation_evidence(evidence)

        RecoverableVaultedProviderDispatchCommercialControlPlane.resume_provider_reconciliation_from_vault(
            plane, evidence["reconciliation_sha256"]
        )
        receipt_missing_after_simulated_interruption = not plane._completion_receipt_path(
            evidence["reconciliation_sha256"]
        ).exists()

        restarted = ReceiptJournaledRecoverableProviderDispatchCommercialControlPlane(
            root,
            authority_snapshot=authority,
            owner_receipts={owner.receipt_id: owner},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        repaired = restarted.resume_provider_reconciliation_from_vault(
            evidence["reconciliation_sha256"]
        )
        retry = restarted.resume_provider_reconciliation_from_vault(
            evidence["reconciliation_sha256"]
        )
        readback = restarted.provider_reconciliation_recovery_completion_readback()
        completion = repaired["recovery_completion_receipt"]

        checks = {
            "dependency_stage_scope_exact": restarted.STAGE_SCOPE
            == ["C03", "C06", "C07", "C11", "C14", "C15"],
            "unknown_outcome_quarantine_enforced": quarantine_enforced,
            "simulated_post_resolution_receipt_gap_created": (
                receipt_missing_after_simulated_interruption
            ),
            "already_resolved_path_detected": repaired["status"]
            == "ALREADY_RESOLVED",
            "missing_completion_receipt_repaired": repaired[
                "completion_receipt_repaired"
            ]
            is True,
            "completion_receipt_hash_bound": bool(
                completion["completion_receipt_sha256"]
            ),
            "completion_receipt_binds_resolution_event": bool(
                completion["resolution_event_sha256"]
            ),
            "exact_retry_idempotent": retry["recovery_completion_receipt"]
            == completion
            and retry["completion_receipt_repaired"] is False,
            "reconciliation_not_reexecuted_for_repair": readback[
                "reconciliation_reexecution_on_receipt_repair"
            ]
            is False,
            "provider_native_reconciliation_remains_blocked": readback[
                "provider_native_reconciliation_authority"
            ]
            == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "external_mutation_not_performed": readback[
                "external_mutation_performed"
            ]
            is False,
            "live_provider_operation_not_proven": readback[
                "live_provider_operation_proven"
            ]
            is False,
        }
        operational = {
            "post_resolution_receipt_repair": True,
            "atomic_content_addressed_completion_receipt": True,
            "exact_retry_idempotency": True,
            "reconciliation_reexecution_on_receipt_repair": False,
            "provider_native_reconciliation_proven": False,
            "external_mutation_performed": False,
        }
        return checks, operational


def prove(repository: Path, output: Path) -> dict[str, Any]:
    programme = json.loads(
        (repository / "alpha_omega_commercial" / "programme.json").read_text(
            encoding="utf-8"
        )
    )
    checkpoint = json.loads(
        (
            repository
            / "alpha_omega_commercial"
            / "provider_reconciliation_recovery_completion_checkpoint.json"
        ).read_text(encoding="utf-8")
    )
    checks, operational = exercise()
    dependency_order = [stage["id"] for stage in programme["stages"]]
    checks["programme_dependency_order_c01_through_c15"] = dependency_order == [
        f"C{index:02d}" for index in range(1, 16)
    ]
    checks["checkpoint_truth_boundary_preserved"] = (
        checkpoint["verified_live_revenue_events"] == 0
        and checkpoint["provider_native_reconciliation"]
        == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
        and checkpoint["full_commercial_maturity"] is False
    )
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("v18 recovery completion proof failed: " + ", ".join(failed))

    receipt = {
        "control_id": "AO-COMMERCIAL-PROVIDER-RECONCILIATION-RECOVERY-COMPLETION-V18",
        "status": "PROVIDER_RECONCILIATION_RECOVERY_COMPLETION_V18_OPERATIONAL_PROOF_VERIFIED",
        "stage_scope": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "checks_required": len(checks),
        "checks_failed": 0,
        "checks": checks,
        "operational_slice": operational,
        "commercial_truth": {
            "service_enabled_platform_prioritised": True,
            "self_service_saas_held": True,
            "verified_live_revenue_events": 0,
            "customer_demand_proven": False,
            "signed_customer_contract_proven": False,
            "payment_provider_operation_proven": False,
            "cloud_run_operation_proven": False,
            "provider_native_reconciliation_proven": False,
            "enterprise_assurance_proven": False,
            "partner_adoption_proven": False,
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
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "provider-reconciliation-recovery-completion-v18-receipt.json"
    destination.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()
    proof = prove(Path(args.root).resolve(), Path(args.output).resolve())
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
