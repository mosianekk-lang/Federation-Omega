from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS = "OWNER_AUTHORITY_PROGRAMME_RECONCILIATION_VERIFIED_GATES_UNCHANGED"
FAILED = "OWNER_AUTHORITY_PROGRAMME_RECONCILIATION_FAILED"
PROGRAMME_ID = "AO-COMMERCIAL-MATURITY-V1"
CONTROL_ID = "AO-COMMERCIAL-OWNER-AUTHORITY-REGISTER-RECONCILIATION-V1"
EXPECTED_STAGE_IDS = [f"C{index:02d}" for index in range(1, 16)]
EXPECTED_SCOPE = ["C12", "C13", "C15"]
EXPECTED_OWNER_RESERVED = {
    "financial commitments",
    "contracts",
    "external communications",
    "consequential releases",
    "revenue recognition confirmation",
}
EXPECTED_OWNER_GATES = {
    "signed_customer_contract",
    "payment_provider_revenue",
    "partner_adoption",
    "external_case_study",
}
EXPECTED_EXTERNAL_GATES = {
    "customer_demand",
    "signed_customer_contract",
    "payment_provider_revenue",
    "live_cloud_provider",
    "enterprise_attestation",
    "partner_adoption",
    "external_case_study",
    "production_scale",
}
EXPECTED_CLOUD_ROUTE = {
    "project_id": "sov-hybrid-suite",
    "region": "africa-south1",
    "service": "federation-omega-operator",
    "path": "/execute",
}
EXPECTED_PROVIDER_STATE = "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
EXPECTED_OWNER_STATE = "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED"


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _valid_sha256_prefixed(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    raw = value.split(":", 1)[1]
    if len(raw) != 64:
        return False
    try:
        int(raw, 16)
    except ValueError:
        return False
    return True


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _stage_index(programme: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], bool]:
    stages = programme.get("stages")
    if not isinstance(stages, list):
        return {}, False
    ids = [stage.get("id") for stage in stages if isinstance(stage, dict)]
    by_id = {stage.get("id"): stage for stage in stages if isinstance(stage, dict) and stage.get("id")}
    valid = ids == EXPECTED_STAGE_IDS
    positions = {stage_id: index for index, stage_id in enumerate(ids)}
    for stage in stages:
        if not isinstance(stage, dict):
            valid = False
            continue
        dependencies = stage.get("depends_on")
        if not isinstance(dependencies, list):
            valid = False
            continue
        current = positions.get(stage.get("id"), -1)
        for dependency in dependencies:
            if dependency not in positions or positions[dependency] >= current:
                valid = False
    return by_id, valid


def verify_owner_authority_programme_reconciliation(
    programme: dict[str, Any],
    checkpoint: dict[str, Any],
    contract: dict[str, Any],
    authority_manifest: dict[str, Any],
) -> dict[str, Any]:
    stages, dependency_order_valid = _stage_index(programme)
    c12, c13, c15 = stages.get("C12", {}), stages.get("C13", {}), stages.get("C15", {})
    proof = checkpoint.get("provider_proof", {})
    drive = checkpoint.get("google_drive_readback", {})
    truth = checkpoint.get("truth_boundary", {})
    owner_authority = checkpoint.get("owner_authority", {})
    external = checkpoint.get("external_gates", {})
    manifest_cloud = authority_manifest.get("cloud_run", {})
    route = {key: manifest_cloud.get(key) for key in EXPECTED_CLOUD_ROUTE}
    issued = _parse_utc(checkpoint.get("verified_at"))
    expires = _parse_utc(proof.get("artifact_expires_at"))

    checks = {
        "programme_identity": programme.get("programme_id") == checkpoint.get("programme_id") == PROGRAMME_ID,
        "checkpoint_control_identity": checkpoint.get("control_id") == CONTROL_ID,
        "stage_sequence_complete": list(stages) == EXPECTED_STAGE_IDS,
        "dependency_order_valid": dependency_order_valid,
        "reconciliation_scope_precise": checkpoint.get("scope") == EXPECTED_SCOPE,
        "scoped_stages_remain_dependency_eligible": (
            c12.get("depends_on") == ["C01", "C06", "C08"]
            and c13.get("depends_on") == ["C01", "C05", "C12"]
            and c15.get("depends_on") == EXPECTED_STAGE_IDS[:-1]
        ),
        "service_enabled_priority_preserved": (
            "service-enabled platform" in str(programme.get("objective", "")).lower()
            and str(stages.get("C11", {}).get("status", "")).startswith("SERVICE_ENABLED_")
        ),
        "owner_reserved_authority_preserved": (
            set(programme.get("owner_reserved_authority", [])) == EXPECTED_OWNER_RESERVED
            and owner_authority.get("state") == EXPECTED_OWNER_STATE
            and owner_authority.get("owner_id") == programme.get("owner")
        ),
        "owner_receipt_contract_exact": (
            contract.get("control_id") == "AO-COMMERCIAL-OWNER-AUTHORITY-RECEIPTS-V1"
            and set(contract.get("owner_reserved_gates", [])) == EXPECTED_OWNER_GATES
            and contract.get("provider_authority", {}).get("current_state") == EXPECTED_OWNER_STATE
            and checkpoint.get("contract_file") == "alpha_omega_commercial/owner_authority_receipt_contract.json"
        ),
        "provider_proof_exact": (
            proof.get("pull_request") == 113
            and proof.get("merge_commit") == "45e79edcb58a7012c900b2efb50f85f92aa3b944"
            and proof.get("head_sha") == "d9c187bb2c626b43d55ada9272a71de53378d5bb"
            and proof.get("workflow_run") == 30864623834
            and proof.get("workflow_job") == 91853678452
            and proof.get("artifact_id") == 8875620056
            and proof.get("artifact_name") == "alpha-omega-commercial-owner-authority-receipts-proof"
            and proof.get("artifact_digest") == "sha256:2422b966559ed3898a8c15b7b4a7b7cef41a18d05f415448508e8df995a0dccf"
            and proof.get("conclusion") == "success"
            and _valid_sha256_prefixed(proof.get("artifact_digest"))
            and issued is not None
            and expires is not None
            and expires > issued
        ),
        "drive_release_readback_preserved": (
            drive.get("file_id") == "1UYV6hyyR68v_WPSfZIEP7mzMGJ07-XKKTyAJsSTW2-c"
            and drive.get("title") == "Alpha Omega Commercial Canonical Provider Authority Reconciliation Release — 2026-08-04"
            and drive.get("modified_at") == "2026-08-03T23:18:35.544Z"
            and drive.get("readback_verified") is True
            and drive.get("shared") is False
        ),
        "canonical_cloud_route_precise": route == EXPECTED_CLOUD_ROUTE,
        "cloud_operation_not_claimed": (
            manifest_cloud.get("status") == "CONTROL_PLANE_PRESENT_LIVE_INVOCATION_UNPROVEN"
            and programme.get("external_evidence_admission", {}).get("provider_authority", {}).get("cloud_run")
            == EXPECTED_PROVIDER_STATE
            and truth.get("cloud_run_operation_proven") is False
        ),
        "external_gate_set_complete": set(external) == EXPECTED_EXTERNAL_GATES,
        "external_gates_unchanged": not any(bool(value) for value in external.values()),
        "zero_revenue_preserved": truth.get("verified_revenue_events") == 0,
        "full_commercial_maturity_not_claimed": truth.get("full_commercial_maturity") is False,
        "customer_and_market_claims_not_made": (
            truth.get("customer_demand_proven") is False
            and truth.get("signed_contract_proven") is False
            and truth.get("payment_proven") is False
            and truth.get("partner_adoption_proven") is False
            and truth.get("external_case_study_proven") is False
            and truth.get("production_scale_proven") is False
        ),
        "stage_truth_boundaries_preserved": (
            "MARKET_PROOF_REQUIRED" in str(c12.get("status", ""))
            and "REVENUE_PROOF_REQUIRED" in str(c13.get("status", ""))
            and "EXTERNAL_MATURITY_GATES_OPEN" in str(c15.get("status", ""))
        ),
    }

    status = STATUS if all(checks.values()) else FAILED
    result = {
        "status": status,
        "programme_id": PROGRAMME_ID,
        "control_id": CONTROL_ID,
        "scope": EXPECTED_SCOPE,
        "checks": checks,
        "provider_proof": proof,
        "google_drive_readback": drive,
        "programme_projection": {
            "C12": {
                "owner_authority_receipt_enforcement": "VERIFIED",
                "external_proof": "MARKET_PROOF_REQUIRED",
            },
            "C13": {
                "owner_authority_receipt_enforcement": "VERIFIED",
                "verified_revenue_events": 0,
                "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            },
            "C15": {
                "owner_authority_receipt_enforcement": "VERIFIED",
                "canonical_status": programme.get("canonical_status"),
                "full_commercial_maturity": False,
            },
        },
        "external_gates": external,
        "owner_authority": owner_authority,
        "truth_boundary": (
            "This receipt proves that the programme register, owner-authority receipt contract, "
            "provider-native PR #113 proof and canonical provider manifest agree. It does not prove "
            "customer demand, a signed contract, payment, revenue, subscriptions, invoices, Cloud Run "
            "operation, enterprise attestation, partner adoption, an external case study or production scale."
        ),
    }
    result["receipt_sha256"] = digest(result)
    return result


def verify_from_paths(
    programme_path: str | Path,
    checkpoint_path: str | Path,
    contract_path: str | Path,
    authority_manifest_path: str | Path,
) -> dict[str, Any]:
    return verify_owner_authority_programme_reconciliation(
        read_json(programme_path),
        read_json(checkpoint_path),
        read_json(contract_path),
        read_json(authority_manifest_path),
    )
