from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_STATUS = "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
CANONICAL_INTEGRITY_STATUS = "CANONICAL_RECEIPT_INTEGRITY_VERIFIED"
EXTERNAL_EVIDENCE_ADMISSION_STATUS = "EXTERNAL_EVIDENCE_ADMISSION_VERIFIED_GATES_UNCHANGED"
AUTHORITY_FRESHNESS_STATUS = "PROVIDER_AUTHORITY_FRESHNESS_RECONCILIATION_VERIFIED"
LIVE_EXPANSION_STATUS = "REVERSIBLE_PROVIDER_EXPANSION_VERIFIED_CLOUD_RUN_PROVIDER_BLOCKED"
C03_STATUS = "LIVE_REVERSIBLE_PROVIDER_AUTHORITY_VERIFIED_CLOUD_RUN_WIF_BLOCK_RECORDED_OWNER_RESERVED_DOMAINS_HELD"
C06_STATUS = "REVERSIBLE_PROVIDER_OPERATIONS_VERIFIED_CLOUD_RUN_PROVIDER_BLOCKED"
C07_STATUS = "SIX_LIVE_REVERSIBLE_PROVIDER_ADAPTERS_VERIFIED_EXTERNAL_PROVIDER_EXPANSION_OPEN"
C11_STATUS = "SERVICE_ENABLED_REVERSIBLE_PROVIDER_OPERATIONS_VERIFIED_SELF_SERVICE_SEND_PAYMENT_AND_CLOUD_HELD"
C12_STATUS = "EVIDENCE_FRAMEWORK_AND_EXTERNAL_ADMISSION_VERIFIED_MARKET_PROOF_REQUIRED"
C13_STATUS = "REFERENCE_REVOPS_AND_PAYMENT_EVIDENCE_ADMISSION_VERIFIED_OWNER_APPROVAL_AND_REVENUE_PROOF_REQUIRED"
C14_STATUS = "REFERENCE_RELIABILITY_VERIFIED_CLOUD_RUN_AND_PRODUCTION_SCALE_PROOF_REQUIRED"
C15_STATUS = "COMMERCIAL_READINESS_VERIFIED_REVERSIBLE_PROVIDER_EXPANSION_VERIFIED_CLOUD_RUN_WIF_BLOCK_RECORDED_EXTERNAL_MATURITY_GATES_OPEN"

EXPECTED_STAGE_IDS = [f"C{index:02d}" for index in range(1, 16)]
EXPECTED_OWNER_RESERVED = {
    "financial commitments",
    "contracts",
    "external communications",
    "consequential releases",
    "revenue recognition confirmation",
}
EXTERNAL_GATE_LABELS = {
    "customer demand and price acceptance": "customer_demand",
    "signed customer contract": "signed_customer_contract",
    "payment-provider revenue receipt": "payment_provider_revenue",
    "live cloud-provider execution": "live_cloud_provider",
    "enterprise assurance or certification": "enterprise_attestation",
    "partner adoption": "partner_adoption",
    "external customer case study": "external_case_study",
    "production scale and recovery evidence": "production_scale",
}
EXPECTED_PROVIDER_AUTHORITY = {
    "github_actions": "FRESH_VERIFIED",
    "google_drive_document_release": "FRESH_VERIFIED_READBACK",
    "google_drive_binary_artifact_transfer": "PROVIDER_BLOCKED_FILE_EGRESS",
    "cloud_run": "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
    "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    "customer_market": "MARKET_PROOF_REQUIRED",
    "partner_market": "MARKET_PROOF_REQUIRED",
    "external_attestation": "UNVERIFIED",
    "live_cloud_operations": "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
    "github_reversible_operations": "FRESH_VERIFIED_OPERATIONAL",
    "google_drive_reversible_operations": "FRESH_VERIFIED_OPERATIONAL",
    "gmail_draft": "FRESH_VERIFIED_OPERATIONAL",
    "google_calendar": "FRESH_VERIFIED_OPERATIONAL",
    "outlook_draft": "FRESH_VERIFIED_OPERATIONAL",
    "canva_transaction": "FRESH_VERIFIED_OPERATIONAL",
}
EXPECTED_FRESHNESS_BLOCKED = {
    "google_drive_binary_artifact_transfer": "PROVIDER_BLOCKED_FILE_EGRESS",
    "cloud_run": "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
    "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    "customer_market": "MARKET_PROOF_REQUIRED",
    "partner_market": "MARKET_PROOF_REQUIRED",
    "external_attestation": "UNVERIFIED",
    "live_cloud_operations": "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
}
EXPECTED_LIVE_PROVIDER_STATES = {
    "github": "FRESH_VERIFIED_OPERATIONAL",
    "google_drive": "FRESH_VERIFIED_OPERATIONAL",
    "gmail_draft": "FRESH_VERIFIED_OPERATIONAL",
    "google_calendar": "FRESH_VERIFIED_OPERATIONAL",
    "outlook_draft": "FRESH_VERIFIED_OPERATIONAL",
    "canva_transaction": "FRESH_VERIFIED_OPERATIONAL",
    "google_cloud_run": "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _valid_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _stage_index(programme: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], bool]:
    stages = programme.get("stages", [])
    stage_ids = [stage.get("id") for stage in stages]
    by_id = {stage.get("id"): stage for stage in stages if stage.get("id")}
    valid = stage_ids == EXPECTED_STAGE_IDS
    positions = {stage_id: index for index, stage_id in enumerate(stage_ids)}
    for stage in stages:
        current = positions.get(stage.get("id"), -1)
        for dependency in stage.get("depends_on", []):
            if dependency not in positions or positions[dependency] >= current:
                valid = False
    return by_id, valid


def verify_programme_register(
    programme: dict[str, Any],
    integrity: dict[str, Any],
    maturity: dict[str, Any],
    commercial_receipt: dict[str, Any],
) -> dict[str, Any]:
    stages, dependency_order_valid = _stage_index(programme)
    c03, c06, c07 = stages.get("C03", {}), stages.get("C06", {}), stages.get("C07", {})
    c11, c12, c13 = stages.get("C11", {}), stages.get("C12", {}), stages.get("C13", {})
    c14, c15 = stages.get("C14", {}), stages.get("C15", {})
    maturity_gates = maturity.get("external_gates", {})
    declared_gate_labels = set(programme.get("external_maturity_gates", []))
    declared_evidence = programme.get("external_gate_evidence", {})
    admission = programme.get("external_evidence_admission", {})
    authority = admission.get("provider_authority", {})
    freshness = programme.get("provider_authority_freshness", {})
    latest_verified = freshness.get("latest_verified", {})
    github_latest = latest_verified.get("github_actions", {})
    drive_latest = latest_verified.get("google_drive_document_release", {})
    expansion = programme.get("live_provider_expansion", {})
    expansion_cloud = expansion.get("cloud_run_block", {})

    gate_evidence_valid = True
    for key in EXTERNAL_GATE_LABELS.values():
        achieved = bool(maturity_gates.get(key))
        evidence = declared_evidence.get(key)
        if achieved != bool(evidence):
            gate_evidence_valid = False

    canonical_reference = programme.get("canonical_receipt", {})
    receipt_integrity = commercial_receipt.get("canonical_receipt_integrity", {})
    c13_proof = commercial_receipt.get("stages", {}).get("C13", {}).get("proof", {})
    old_cloud_boundary = commercial_receipt.get("truth_boundaries", {}).get("cloud_run")

    checks = {
        "programme_identity": programme.get("programme_id") == "AO-COMMERCIAL-MATURITY-V1",
        "service_enabled_priority_preserved": (
            "service-enabled platform" in programme.get("objective", "").lower()
            and c11.get("status", "").startswith("SERVICE_ENABLED_")
            and "VERIFIED" in c11.get("status", "")
        ),
        "stage_sequence_complete": list(stages) == EXPECTED_STAGE_IDS,
        "dependency_order_valid": dependency_order_valid,
        "c15_depends_on_c01_c14": c15.get("depends_on") == EXPECTED_STAGE_IDS[:-1],
        "canonical_status_matches_maturity": programme.get("canonical_status") == maturity.get("canonical_status") == CANONICAL_STATUS,
        "canonical_integrity_status_matches": (
            programme.get("canonical_receipt_integrity")
            == integrity.get("status")
            == receipt_integrity.get("status")
            == CANONICAL_INTEGRITY_STATUS
        ),
        "external_evidence_admission_verified": (
            admission.get("status") == EXTERNAL_EVIDENCE_ADMISSION_STATUS
            and admission.get("proof_scope") == "C12_C13_C15_EXTERNAL_EVIDENCE_ADMISSION"
            and "external provider-native evidence" in admission.get("admission_rule", "").lower()
        ),
        "provider_authority_scopes_precise": authority == EXPECTED_PROVIDER_AUTHORITY,
        "provider_authority_freshness_verified": (
            freshness.get("status") == AUTHORITY_FRESHNESS_STATUS
            and freshness.get("proof_scope") == "C03_C10_C12_C13_C15_PROVIDER_AUTHORITY_FRESHNESS"
            and freshness.get("source_observations_file") == "alpha_omega_commercial/provider_authority_observations.json"
            and freshness.get("external_gate_effect") == "UNCHANGED"
            and freshness.get("owner_authority_effect") == "UNCHANGED"
        ),
        "authority_freshness_operational_evidence_complete": (
            github_latest.get("state") == "FRESH_VERIFIED"
            and isinstance(github_latest.get("workflow_run"), int)
            and isinstance(github_latest.get("artifact_id"), int)
            and drive_latest.get("state") == "FRESH_VERIFIED_READBACK"
            and bool(drive_latest.get("file_id"))
            and _valid_sha256(drive_latest.get("content_sha256"))
        ),
        "authority_freshness_blocked_domains_preserved": freshness.get("blocked_or_unverified") == EXPECTED_FRESHNESS_BLOCKED,
        "live_provider_expansion_verified": (
            expansion.get("status") == LIVE_EXPANSION_STATUS
            and expansion.get("proof_scope") == "C03_C06_C07_C11_C14_C15_REVERSIBLE_PROVIDER_EXPANSION"
            and expansion.get("receipt_file") == "alpha_omega_commercial/live_provider_expansion_receipt.json"
            and isinstance(expansion.get("workflow_run"), int)
            and isinstance(expansion.get("workflow_job"), int)
            and isinstance(expansion.get("artifact_id"), int)
            and expansion.get("artifact_digest", "").startswith("sha256:")
            and _valid_sha256(expansion.get("receipt_sha256"))
            and expansion.get("external_gate_effect") == "UNCHANGED"
            and expansion.get("owner_authority_effect") == "UNCHANGED"
            and expansion.get("verified_revenue_events") == 0
            and not expansion.get("full_commercial_maturity")
        ),
        "live_provider_states_precise": expansion.get("provider_states") == EXPECTED_LIVE_PROVIDER_STATES,
        "cloud_run_wif_block_precise": (
            expansion_cloud.get("reason") == "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED"
            and expansion_cloud.get("previous_exact_error") == "invalid_target"
            and expansion_cloud.get("mutation_performed") is False
            and bool(expansion_cloud.get("workload_identity_provider"))
        ),
        "c03_status_verified": c03.get("status") == C03_STATUS,
        "c06_status_verified": c06.get("status") == C06_STATUS,
        "c07_status_verified": c07.get("status") == C07_STATUS,
        "c11_status_verified": c11.get("status") == C11_STATUS,
        "c12_admission_status_verified": c12.get("status") == C12_STATUS,
        "c13_admission_status_verified": c13.get("status") == C13_STATUS,
        "c14_status_verified": c14.get("status") == C14_STATUS,
        "c15_register_status_verified": c15.get("status") == C15_STATUS,
        "integrity_checks_pass": bool(integrity.get("checks")) and all(integrity.get("checks", {}).values()),
        "technical_reference_ready": bool(maturity.get("technical_reference_ready")),
        "full_commercial_maturity_not_claimed": not bool(maturity.get("full_commercial_maturity")),
        "external_gate_labels_complete": declared_gate_labels == set(EXTERNAL_GATE_LABELS),
        "external_gate_values_complete": set(maturity_gates) == set(EXTERNAL_GATE_LABELS.values()),
        "external_gate_evidence_consistent": gate_evidence_valid,
        "owner_reserved_authority_preserved": set(programme.get("owner_reserved_authority", [])) == EXPECTED_OWNER_RESERVED,
        "zero_revenue_preserved": c13_proof.get("verified_revenue_events") == 0,
        "cloud_run_not_claimed": (
            old_cloud_boundary == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and expansion.get("provider_states", {}).get("google_cloud_run") == "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED"
        ),
        "canonical_artifact_reference_matches": (
            canonical_reference.get("pull_request") == 93
            and canonical_reference.get("merge_commit") == "a897cb4788da76f11702b12dc0c5ed06c8b9acfa"
            and canonical_reference.get("workflow_run") == 30835362760
            and canonical_reference.get("artifact_id") == 8864581266
            and canonical_reference.get("artifact_digest") == "sha256:f011a0c70c979de6a714bef5d582c4d0c9c96e8cda9879fc09154195e5b1725d"
            and canonical_reference.get("integrity_receipt_sha256") == "1908449a171078d4592199cddabdc8187df2d2069776df838a0b027e56f6a7e0"
            and canonical_reference.get("google_drive_release_file_id") == "1L4ysPqtf8x2c9E-3dwVi4KDt5QwR53Oc4suFZXqSe2Q"
        ),
    }

    result = {
        "status": "PROGRAMME_REGISTER_INTEGRITY_VERIFIED" if all(checks.values()) else "PROGRAMME_REGISTER_INTEGRITY_FAILED",
        "verified_at": utc_now(),
        "programme_id": programme.get("programme_id"),
        "canonical_status": programme.get("canonical_status"),
        "canonical_receipt_integrity": programme.get("canonical_receipt_integrity"),
        "external_evidence_admission": admission.get("status"),
        "provider_authority_freshness": freshness.get("status"),
        "live_provider_expansion": expansion.get("status"),
        "checks": checks,
        "external_gates": maturity_gates,
        "provider_authority": authority,
        "owner_reserved_authority": sorted(EXPECTED_OWNER_RESERVED),
        "truth_boundary": (
            "This receipt proves programme-register consistency, six reversible provider operations, exact Cloud Run WIF blocking before mutation, "
            "provider freshness, persistence and rollback. It does not establish customer demand, a signed contract, payment-provider revenue, "
            "Cloud Run operation, enterprise attestation, partner adoption, an external case study or production-scale evidence."
        ),
    }
    result["receipt_sha256"] = digest(result)
    return result


def verify_from_paths(programme_path: str | Path, artifact_root: str | Path) -> dict[str, Any]:
    root = Path(artifact_root)
    return verify_programme_register(
        read_json(programme_path),
        read_json(root / "canonical-receipt-integrity.json"),
        read_json(root / "commercial-maturity.json"),
        read_json(root / "commercial-c10-c15-receipt.json"),
    )
