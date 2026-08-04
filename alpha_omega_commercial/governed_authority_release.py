from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


STATUS = "GOVERNED_COMMERCIAL_AUTHORITY_V2_RELEASE_VERIFIED_EXTERNAL_GATES_UNCHANGED"
EXPECTED_RUN_KEYS = {
    "C01_C05",
    "C06_C09",
    "C10_C15",
    "provider_authority",
    "governed_authority",
    "github_control_plane",
    "superior_logic_ci",
    "repository_leak_guard",
}
EXPECTED_OWNER_AUTHORITY = {
    "financial_commitments": "OWNER_RESERVED",
    "contracts": "OWNER_RESERVED",
    "external_communications": "OWNER_RESERVED",
    "consequential_releases": "OWNER_RESERVED",
    "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
}


def digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def valid_sha256(value: Any, *, prefixed: bool = False) -> bool:
    if prefixed:
        if not isinstance(value, str) or not value.startswith("sha256:"):
            return False
        value = value[7:]
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def verify_release(
    receipt: dict[str, Any],
    checkpoint: dict[str, Any],
    programme: dict[str, Any],
) -> dict[str, Any]:
    receipt_for_hash = dict(receipt)
    receipt_hash = receipt_for_hash.pop("receipt_sha256", None)
    proof = receipt.get("provider_native_proof", {})
    runs = proof.get("final_head_runs", {})
    drive = receipt.get("google_drive_release", {})
    truth = receipt.get("truth_boundary", {})
    implementation = receipt.get("implementation", {})

    checkpoint_proof = checkpoint.get("provider_proof", {})
    checkpoint_drive = checkpoint.get("google_drive_release", {})
    checkpoint_receipt = checkpoint.get("release_receipt", {})

    checks = {
        "programme_identity": (
            receipt.get("programme_id")
            == checkpoint.get("programme_id")
            == programme.get("programme_id")
            == "AO-COMMERCIAL-MATURITY-V1"
        ),
        "release_status_exact": (
            receipt.get("status") == checkpoint.get("status") == STATUS
        ),
        "receipt_hash_valid": valid_sha256(receipt_hash)
        and digest(receipt_for_hash) == receipt_hash,
        "canonical_programme_boundary_preserved": (
            programme.get("canonical_status")
            == "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
            and programme.get("external_gate_evidence") == {}
        ),
        "implementation_binding_exact": (
            implementation.get("pull_request") == 118
            and implementation.get("head_sha")
            == "3f9512e721c3e573f5531c98320c55f72a927506"
            and implementation.get("merge_commit")
            == "3102a12f4fa5e54d70c9eeeca493a006e9c7cdae"
            and implementation.get("canonical_class")
            == "GovernedCommercialAssuranceControlPlane"
            and implementation.get("legacy_class_state")
            == "REFERENCE_ONLY_NOT_CANONICAL"
        ),
        "provider_proof_complete": (
            proof.get("governed_authority_workflow_run") == 30871321933
            and proof.get("artifact_id") == 8877970163
            and proof.get("artifact_name")
            == "alpha-omega-commercial-governed-authority-v2-proof"
            and valid_sha256(proof.get("artifact_digest"), prefixed=True)
            and valid_sha256(proof.get("embedded_receipt_sha256"))
            and valid_sha256(proof.get("receipt_file_sha256"))
            and valid_sha256(proof.get("canonical_api_readback_sha256"))
            and set(runs) == EXPECTED_RUN_KEYS
            and all(isinstance(run_id, int) and run_id > 0 for run_id in runs.values())
            and proof.get("all_conclusions") == "success"
        ),
        "checkpoint_provider_proof_matches": (
            checkpoint_proof.get("state") == "FINAL_HEAD_PROVIDER_NATIVE_CI_VERIFIED"
            and checkpoint_proof.get("workflow_run")
            == proof.get("governed_authority_workflow_run")
            and checkpoint_proof.get("artifact_id") == proof.get("artifact_id")
            and checkpoint_proof.get("artifact_digest") == proof.get("artifact_digest")
            and checkpoint_proof.get("final_head_commercial_runs") == runs
            and checkpoint_proof.get("all_conclusions") == "success"
        ),
        "drive_release_complete": (
            drive.get("file_id") == "1MlRXCSMtnW5okJVTtxRlTrP3u8wdl_ehWhMw4s3md5k"
            and drive.get("mime_type") == "application/vnd.google-apps.document"
            and drive.get("exported_text_size_bytes") == 4088
            and valid_sha256(drive.get("exported_text_sha256"))
            and drive.get("readback_verified") is True
            and drive.get("shared") is False
            and drive.get("owner") == "mosianekk@gmail.com"
        ),
        "checkpoint_drive_matches": checkpoint_drive == drive,
        "checkpoint_receipt_binding_exact": (
            checkpoint_receipt.get("file")
            == "alpha_omega_commercial/governed_authority_release_receipt.json"
            and checkpoint_receipt.get("receipt_sha256") == receipt_hash
        ),
        "external_gates_all_open": (
            set(receipt.get("external_gates", {}))
            == {
                "customer_demand",
                "signed_customer_contract",
                "payment_provider_revenue",
                "live_cloud_provider",
                "enterprise_attestation",
                "partner_adoption",
                "external_case_study",
                "production_scale",
            }
            and not any(receipt.get("external_gates", {}).values())
            and receipt.get("external_gates") == checkpoint.get("external_gates")
        ),
        "zero_revenue_truth_preserved": (
            truth.get("verified_live_revenue_events") == 0
            and truth.get("mock_provider_conformance_events") == 1
            and truth.get("mock_provider_conformance_is_revenue") is False
            and checkpoint.get("truth_boundary", {}).get("verified_revenue_events") == 0
        ),
        "cloud_and_maturity_not_claimed": (
            truth.get("cloud_run_operation_proven") is False
            and truth.get("full_commercial_maturity") is False
            and checkpoint.get("truth_boundary", {}).get("cloud_run_operation_proven")
            is False
            and checkpoint.get("truth_boundary", {}).get("full_commercial_maturity")
            is False
        ),
        "owner_authority_preserved": (
            receipt.get("owner_authority") == EXPECTED_OWNER_AUTHORITY
            and checkpoint.get("owner_authority") == EXPECTED_OWNER_AUTHORITY
        ),
    }
    return {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "control_id": "AO-COMMERCIAL-GOVERNED-AUTHORITY-RELEASE-RECONCILIATION-V1",
        "status": (
            "GOVERNED_AUTHORITY_RELEASE_RECONCILIATION_VERIFIED"
            if all(checks.values())
            else "GOVERNED_AUTHORITY_RELEASE_RECONCILIATION_FAILED"
        ),
        "checks": checks,
        "release_receipt_sha256": receipt_hash,
        "external_gates": dict(receipt.get("external_gates", {})),
        "verified_live_revenue_events": truth.get("verified_live_revenue_events"),
        "full_commercial_maturity": truth.get("full_commercial_maturity"),
    }


def prove(
    receipt_path: str | Path,
    checkpoint_path: str | Path,
    programme_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    result = verify_release(
        load(receipt_path),
        load(checkpoint_path),
        load(programme_path),
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(result["checks"].values()):
        raise SystemExit("governed authority release reconciliation failed")
    return result
