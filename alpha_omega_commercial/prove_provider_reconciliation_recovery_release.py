from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from provider_reconciliation_recovery import (
    RecoverableVaultedProviderDispatchCommercialControlPlane,
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def validate(repository: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    commercial = repository / "alpha_omega_commercial"
    programme = load(commercial / "programme.json")
    implementation = load(commercial / "provider_reconciliation_recovery_checkpoint.json")
    receipt = load(commercial / "provider_reconciliation_recovery_release_receipt.json")
    release = load(commercial / "provider_reconciliation_recovery_release_checkpoint.json")
    api = load(commercial / "canonical_commercial_api_effective_v17.json")
    maturity = load(commercial / "programme_maturity_effective_v17.json")
    institution_text = (commercial / "institution_reconciliation_checkpoint.json").read_text(encoding="utf-8")

    receipt_payload = dict(receipt)
    observed_receipt_sha256 = receipt_payload.pop("receipt_sha256", None)
    dependency_order = [stage["id"] for stage in programme["stages"]]
    provider = receipt["provider_proof"]
    drive = receipt["google_drive_release"]
    checks = {
        "dependency_order_c01_through_c15": dependency_order == [f"C{index:02d}" for index in range(1, 16)],
        "release_dependency_order_exact": receipt["dependency_order"] == dependency_order,
        "stage_scope_dependency_ordered": receipt["stage_scope"] == ["C03", "C06", "C07", "C11", "C14", "C15"],
        "implementation_release_exact": receipt["implementation_release"] == {
            "pull_request": 158,
            "implementation_head": "97aeb7bb625463b51a879354758024b344eb1d05",
            "merge_commit": "03e2c9c096d3b4eee846992f2f723f6f36ed602c",
            "merged": True,
        },
        "implementation_checkpoint_verified": implementation["status"] == "PROVIDER_RECONCILIATION_RECOVERY_V17_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED",
        "provider_proof_exact": provider["workflow_run"] == 30927745566
        and provider["workflow_job"] == 92054345687
        and provider["artifact_id"] == 8899813315
        and provider["artifact_digest"] == "sha256:c9b05412459ca2e8c07df162aad8bc535715d26b86e82078d50d9707888c010e"
        and provider["receipt_file_sha256"] == "3c879130e32a9a78800e416178f87d8e24f34612b1564c67713e620a7ecda56e"
        and provider["checks_required"] == 12
        and provider["checks_failed"] == 0
        and provider["regression_tests_passed"] == 59,
        "provider_job_and_artifact_inspected": provider["job_steps_readback_verified"] is True
        and provider["all_triggered_workflows"] == 31
        and provider["all_conclusions_success"] is True,
        "drive_identity_and_metadata_exact": drive["file_id"] == "18SwQIrE6KL39qkKKlvxM_aTxXzZLoWac82LLLX5qf1M"
        and drive["created_time"] == "2026-08-04T16:11:10.872Z"
        and drive["modified_time"] == "2026-08-04T16:11:36.746Z",
        "drive_export_hash_exact": drive["export_size_bytes"] == 4924
        and drive["export_sha256"] == "f7153ebf0c82920e5f67f501bb2a35c7c0d8e96c2390f545b77bad99ac8e2ffc",
        "drive_private_owner_controlled": drive["readback_verified"] is True
        and drive["shared"] is False
        and drive["owner"] == "mosianekk@gmail.com",
        "release_receipt_digest": observed_receipt_sha256 == canonical_digest(receipt_payload)
        == "791ec5dc2b8aa4ab233c98d716587758f9ca94dd717e6bb56ef3205aa4c26a7f",
        "release_checkpoint_bound": release["release_receipt_sha256"] == observed_receipt_sha256
        and release["provider_proof_artifact_id"] == provider["artifact_id"]
        and release["google_drive_export_sha256"] == drive["export_sha256"],
        "canonical_api_v17_effective": api["canonical_class"] == RecoverableVaultedProviderDispatchCommercialControlPlane.__name__
        and api["implementation_provider_proof"]["state"] == "PROVIDER_PROOF_VERIFIED",
        "service_enabled_platform_first": api["service_enabled_platform_prioritised"] is True
        and api["self_service_saas_held"] is True,
        "recovery_controls_verified": api["controls"]["recoverable_evidence_classification"] is True
        and api["controls"]["recoverable_evidence_prune_protection"] is True
        and api["controls"]["deterministic_vault_replay"] is True
        and api["controls"]["exact_replay_idempotency"] is True,
        "provider_boundaries_unchanged": maturity["external_gates"]["provider_native_reconciliation"] == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
        and maturity["external_gates"]["distributed_provider_exactly_once"] == "PROVIDER_PROOF_REQUIRED",
        "verified_live_revenue_zero": maturity["verified_live_revenue_events"] == 0
        and receipt["commercial_truth"]["verified_live_revenue_events"] == 0,
        "full_commercial_maturity_not_claimed": maturity["full_commercial_maturity"] is False
        and receipt["commercial_truth"]["full_commercial_maturity"] is False,
        "institution_and_owner_boundaries_preserved": "P13" in institution_text
        and "P15" in institution_text
        and set(receipt["owner_authority"].values()) == {
            "OWNER_RESERVED",
            "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        },
    }
    return checks, receipt


def prove(repository: Path, output: Path) -> dict[str, Any]:
    checks, receipt = validate(repository)
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("v17 recovery release proof failed: " + ", ".join(failed))
    proof = {
        "control_id": "AO-COMMERCIAL-PROVIDER-RECONCILIATION-RECOVERY-V17-RELEASE-PROOF",
        "status": receipt["status"],
        "stage_scope": receipt["stage_scope"],
        "checks_required": len(checks),
        "checks_failed": 0,
        "checks": checks,
        "implementation_release": receipt["implementation_release"],
        "provider_proof": receipt["provider_proof"],
        "google_drive_release": receipt["google_drive_release"],
        "commercial_truth": receipt["commercial_truth"],
        "owner_authority": receipt["owner_authority"],
        "external_gate_effect": receipt["external_gate_effect"],
        "release_receipt_sha256": receipt["receipt_sha256"],
    }
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "provider-reconciliation-recovery-v17-release-proof.json"
    destination.write_text(json.dumps(proof, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()
    proof = prove(Path(args.root).resolve(), Path(args.output).resolve())
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
