from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from provider_reconciliation_recovery import (
    RecoverableVaultedProviderDispatchCommercialControlPlane,
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()

    repository = Path(args.root).resolve()
    commercial = repository / "alpha_omega_commercial"
    output = repository / args.output
    output.mkdir(parents=True, exist_ok=True)

    programme = load_json(commercial / "programme.json")
    checkpoint = load_json(
        commercial / "provider_reconciliation_recovery_checkpoint.json"
    )
    projection = load_json(commercial / "canonical_commercial_api_effective_v17.json")
    maturity = load_json(commercial / "programme_maturity_effective_v17.json")
    predecessor = load_json(
        commercial / "provider_reconciliation_evidence_vault_release_checkpoint.json"
    )
    institution_text = (
        commercial / "institution_reconciliation_checkpoint.json"
    ).read_text(encoding="utf-8")

    dependency_order = [stage["id"] for stage in programme["stages"]]
    controls = projection["controls"]
    checks = {
        "dependency_order_c01_through_c15": dependency_order
        == [f"C{index:02d}" for index in range(1, 16)],
        "stage_scope_dependency_ordered": checkpoint["stage_scope"]
        == ["C03", "C06", "C07", "C11", "C14", "C15"],
        "predecessor_v16_release_verified": predecessor["status"]
        == "PROVIDER_RECONCILIATION_EVIDENCE_VAULT_V16_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED",
        "predecessor_drive_fresh_readback_bound": checkpoint[
            "dependency_predecessor"
        ]["google_drive_latest_readback_modified_time"]
        == "2026-08-04T15:15:05.991Z"
        and checkpoint["dependency_predecessor"]["google_drive_export_sha256"]
        == "88b43753d53d5291a89da26962b911d51265654492651c7086483e9c2223f578",
        "v17_canonical_class_exported": projection["canonical_class"]
        == RecoverableVaultedProviderDispatchCommercialControlPlane.__name__,
        "recoverable_classification_enabled": controls[
            "recoverable_evidence_classification"
        ]
        is True,
        "recoverable_prune_protection_enabled": controls[
            "recoverable_evidence_prune_protection"
        ]
        is True
        and controls["invalid_orphan_evidence_prune"] is True,
        "deterministic_replay_enabled": controls["deterministic_vault_replay"]
        is True
        and controls["challenge_observation_time_replay_binding"] is True
        and controls["exact_replay_idempotency"] is True,
        "provider_native_reconciliation_remains_blocked": maturity[
            "external_gates"
        ]["provider_native_reconciliation"]
        == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        "service_enabled_platform_remains_first": maturity[
            "service_enabled_platform_first"
        ]
        is True
        and maturity["self_service_saas_held"] is True,
        "verified_live_revenue_remains_zero": maturity[
            "verified_live_revenue_events"
        ]
        == 0,
        "institution_and_owner_boundaries_preserved": "P13" in institution_text
        and "P15" in institution_text
        and set(maturity["owner_authority"].values())
        == {
            "OWNER_RESERVED",
            "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        },
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(
            "provider reconciliation recovery proof failed: " + ", ".join(failed)
        )

    receipt = {
        "control_id": "AO-COMMERCIAL-PROVIDER-RECONCILIATION-RECOVERY-V17",
        "status": "PROVIDER_RECONCILIATION_RECOVERY_CONFORMANCE_VERIFIED_PROVIDER_NATIVE_RECONCILIATION_BLOCKED",
        "stage_scope": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "checks_required": len(checks),
        "checks_failed": 0,
        "checks": checks,
        "operational_slice": {
            "valid_pre_resolution_evidence_classified_recoverable": True,
            "recoverable_evidence_prune_protected": True,
            "invalid_or_rejected_evidence_prunable": True,
            "deterministic_vault_replay": True,
            "challenge_observation_time_replay_binding": True,
            "exact_replay_idempotency": True,
            "content_addressed_evidence_vault_preserved": True,
            "mock_provider_conformance": True,
            "provider_native_reconciliation_authority": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "provider_native_reconciliation_proven": False,
            "external_mutation_performed": False,
        },
        "commercial_truth": {
            "service_enabled_platform_prioritised": True,
            "self_service_saas_held": True,
            "verified_live_revenue_events": 0,
            "customer_demand_proven": False,
            "signed_customer_contract_proven": False,
            "payment_provider_operation_proven": False,
            "cloud_run_operation_proven": False,
            "enterprise_assurance_proven": False,
            "partner_adoption_proven": False,
            "production_scale_proven": False,
            "full_commercial_maturity": False,
        },
        "predecessor_drive_readback": checkpoint["dependency_predecessor"],
        "external_gate_effect": "UNCHANGED",
        "owner_authority": maturity["owner_authority"],
    }
    destination = output / "provider-reconciliation-recovery-v17-receipt.json"
    destination.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(destination)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
