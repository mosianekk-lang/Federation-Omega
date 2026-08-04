from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from authority_snapshot import digest
from provider_dispatch_outcome_reconciliation import OutcomeReconciledProviderDispatchCommercialControlPlane

ORDER = [f"C{i:02d}" for i in range(1, 16)]
DEPS = {
    "C01": [], "C02": ["C01"], "C03": ["C02"],
    "C04": ["C02", "C03"], "C05": ["C02"],
    "C06": ["C03", "C04"], "C07": ["C03"],
    "C08": ["C01", "C05", "C07"], "C09": ["C05", "C08"],
    "C10": ["C02", "C03", "C06"],
    "C11": ["C04", "C05", "C06", "C08", "C10"],
    "C12": ["C01", "C06", "C08"],
    "C13": ["C01", "C05", "C12"],
    "C14": ["C05", "C06", "C07", "C11"],
    "C15": ORDER[:-1],
}
SCOPE = ["C03", "C06", "C07", "C11", "C14", "C15"]
OWNER = {
    "financial_commitments": "OWNER_RESERVED",
    "contracts": "OWNER_RESERVED",
    "external_communications": "OWNER_RESERVED",
    "consequential_releases": "OWNER_RESERVED",
    "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_valid(value: dict[str, Any]) -> bool:
    payload = dict(value)
    observed = payload.pop("receipt_sha256", None)
    return observed == digest(payload)


def validate(root: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    commercial = root / "alpha_omega_commercial"
    programme = load(commercial / "programme.json")
    checkpoint = load(commercial / "provider_dispatch_outcome_reconciliation_checkpoint.json")
    receipt = load(commercial / "provider_dispatch_outcome_reconciliation_release_receipt.json")
    release = load(commercial / "provider_dispatch_outcome_reconciliation_release_checkpoint.json")
    api = load(commercial / "canonical_commercial_api_effective_v14.json")
    maturity = load(commercial / "programme_maturity_effective_v14.json")
    institution = load(commercial / "institution_reconciliation_checkpoint.json")
    stages = programme["stages"]
    proof = checkpoint["operational_proof_gate"]
    drive = checkpoint["google_drive_release"]
    truth = checkpoint["commercial_truth"]
    false_claims = (
        "customer_demand_proven", "signed_customer_contract_proven",
        "payment_provider_operation_proven", "cloud_run_operation_proven",
        "enterprise_attestation_proven", "partner_adoption_proven",
        "external_customer_case_study_proven", "production_scale_proven",
        "provider_native_reconciliation_proven",
        "distributed_provider_exactly_once_proven", "full_commercial_maturity",
    )
    checks = {
        "programme_identity": programme["programme_id"] == "AO-COMMERCIAL-MATURITY-V1" and "service-enabled platform" in programme["objective"],
        "dependency_order": [x["id"] for x in stages] == ORDER,
        "dependency_graph": {x["id"]: x["depends_on"] for x in stages} == DEPS,
        "eligible_stage_scope": checkpoint["candidate_projection"]["stage_scope"] == SCOPE == receipt["stage_scope"],
        "implementation_identity": checkpoint["implementation_release"] == {"pull_request": 150, "implementation_head": "6f61c5c7b654d70ec45fff3976f200259a76eb1a", "merge_commit": "6afd09e31dcea910f4e64de59ca776aae834d261", "merged": True},
        "provider_proof_identity": proof["workflow_run"] == 30913614473 and proof["workflow_job"] == 92006113662 and proof["artifact_id"] == 8894094769 and proof["artifact_digest"] == "sha256:8674a3e2a53e046270a1b4ee1b9ec2fb6c6e88a0430c53fc8f97960d3a6d27a4",
        "provider_proof_passed": proof["checks_required"] == 12 and proof["checks_failed"] == 0 and proof["job_steps_readback_verified"] and proof["all_triggered_workflows"] == 31 and proof["all_conclusions_success"],
        "provider_artifact_unexpired": datetime.fromisoformat(proof["artifact_expires_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc),
        "regression_register_bound": len(checkpoint["final_head_regression_runs"]) == 31 and checkpoint["final_head_regression_runs"] == receipt["regression_runs"],
        "drive_identity": drive["file_id"] == "1RkHNK4WDim8BKjEvd-_lUF_EIeA6zqrMAcFhNZGF-30" and drive["modified_time"] == "2026-08-04T13:28:37.044Z",
        "drive_private_readback": drive["readback_verified"] and not drive["shared"] and drive["owner"] == "mosianekk@gmail.com",
        "drive_export_hash": drive["export_size_bytes"] == 7731 and drive["export_sha256"] == "d43584cebbd41f3ac6c36c2a2ab1557c502ec6725c03e29573f4e0837f29336f",
        "release_receipt_digest": receipt_valid(receipt),
        "release_checkpoint_binding": release["release_receipt_sha256"] == receipt["receipt_sha256"] and release["provider_proof_artifact_id"] == 8894094769 and release["google_drive_file_id"] == drive["file_id"],
        "effective_api": api["capability_revision"] == OutcomeReconciledProviderDispatchCommercialControlPlane.CAPABILITY_REVISION and api["canonical_class"] == OutcomeReconciledProviderDispatchCommercialControlPlane.__name__,
        "effective_maturity": maturity["dependency_order"] == ORDER and maturity["advanced_internal_slice"]["capability_revision"] == OutcomeReconciledProviderDispatchCommercialControlPlane.CAPABILITY_REVISION,
        "service_first": api["service_enabled_platform_prioritised"] and api["self_service_saas_held"] and maturity["service_enabled_platform_first"] and maturity["self_service_saas_held"],
        "institution_boundary": checkpoint["institution_projection"] == institution["institution_projection"],
        "commercial_truth": truth["verified_live_revenue_events"] == 0 and all(truth[x] is False for x in false_claims),
        "provider_and_owner_boundaries": checkpoint["provider_boundaries"]["cloud_run"] == "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE" and checkpoint["provider_boundaries"]["payment_provider"] == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY" and checkpoint["provider_boundaries"]["provider_native_reconciliation"] == "PROVIDER_PROOF_REQUIRED" and checkpoint["owner_authority"] == OWNER == receipt["owner_authority"],
    }
    evidence = {
        "implementation_checkpoint_sha256": file_sha(commercial / "provider_dispatch_outcome_reconciliation_checkpoint.json"),
        "release_receipt_file_sha256": file_sha(commercial / "provider_dispatch_outcome_reconciliation_release_receipt.json"),
        "release_checkpoint_sha256": file_sha(commercial / "provider_dispatch_outcome_reconciliation_release_checkpoint.json"),
        "effective_api_sha256": file_sha(commercial / "canonical_commercial_api_effective_v14.json"),
        "effective_maturity_sha256": file_sha(commercial / "programme_maturity_effective_v14.json"),
        "provider_proof": proof,
        "google_drive_release": drive,
    }
    return checks, evidence


def prove(root: Path, output: Path) -> dict[str, Any]:
    checks, evidence = validate(root)
    result = {
        "control_id": "AO-COMMERCIAL-PROVIDER-DISPATCH-OUTCOME-RECONCILIATION-V14-RELEASE-PROOF",
        "status": "PROVIDER_DISPATCH_OUTCOME_RECONCILIATION_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED",
        "stage_scope": SCOPE,
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": sum(not x for x in checks.values()),
        "evidence": evidence,
        "commercial_truth": {"service_enabled_platform_prioritised": True, "self_service_saas_held": True, "verified_live_revenue_events": 0, "provider_native_reconciliation_proven": False, "payment_provider_operation_proven": False, "cloud_run_operation_proven": False, "full_commercial_maturity": False},
        "external_gate_effect": "UNCHANGED",
        "owner_authority": OWNER,
    }
    result["proof_sha256"] = digest(result)
    if result["checks_failed"]:
        raise RuntimeError("release proof failed: " + ", ".join(k for k, v in checks.items() if not v))
    output.mkdir(parents=True, exist_ok=True)
    (output / "provider-dispatch-outcome-reconciliation-release-proof.json").write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    print(json.dumps(prove(args.root.resolve(), args.output.resolve()), indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
