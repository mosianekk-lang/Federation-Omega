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
CANONICAL_RECONCILIATION_STATUS = "CANONICAL_PROVIDER_ROUTE_ALIGNED_IDENTITY_AUTHORITY_UNAVAILABLE"

C03_STATUS = "CANONICAL_PROVIDER_ROUTE_ALIGNED_SIX_REVERSIBLE_PROVIDERS_VERIFIED_IDENTITY_AUTHORITY_UNAVAILABLE"
C06_STATUS = "REVERSIBLE_PROVIDER_OPERATIONS_VERIFIED_CANONICAL_CLOUD_ROUTE_ALIGNED_LIVE_SLA_BLOCKED"
C07_STATUS = "SIX_REVERSIBLE_PROVIDER_ADAPTERS_VERIFIED_CANONICAL_CLOUD_ADAPTER_PACKAGED_AUTHORITY_BLOCKED"
C11_STATUS = "SERVICE_ENABLED_PLATFORM_VERIFIED_CANONICAL_CLOUD_ROUTE_ALIGNED_SELF_SERVICE_HELD"
C12_STATUS = "EVIDENCE_FRAMEWORK_AND_EXTERNAL_ADMISSION_VERIFIED_MARKET_PROOF_REQUIRED"
C13_STATUS = "REFERENCE_REVOPS_AND_PAYMENT_EVIDENCE_ADMISSION_VERIFIED_OWNER_APPROVAL_AND_REVENUE_PROOF_REQUIRED"
C14_STATUS = "REFERENCE_RELIABILITY_VERIFIED_CANONICAL_CLOUD_ROUTE_ALIGNED_PRODUCTION_PROOF_REQUIRED"
C15_STATUS = "COMMERCIAL_READINESS_VERIFIED_CANONICAL_PROVIDER_ROUTE_ALIGNED_EXTERNAL_MATURITY_GATES_OPEN"

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
    "cloud_run": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
    "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    "customer_market": "MARKET_PROOF_REQUIRED",
    "partner_market": "MARKET_PROOF_REQUIRED",
    "external_attestation": "UNVERIFIED",
    "live_cloud_operations": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
    "github_reversible_operations": "FRESH_VERIFIED_OPERATIONAL",
    "google_drive_reversible_operations": "FRESH_VERIFIED_OPERATIONAL",
    "gmail_draft": "FRESH_VERIFIED_OPERATIONAL",
    "google_calendar": "FRESH_VERIFIED_OPERATIONAL",
    "outlook_draft": "FRESH_VERIFIED_OPERATIONAL",
    "canva_transaction": "FRESH_VERIFIED_OPERATIONAL",
}
# Historical snapshots remain valid evidence and must not be rewritten as current authority.
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
EXPECTED_CANONICAL_ROUTE = {
    "project_id": "sov-hybrid-suite",
    "region": "africa-south1",
    "service": "federation-omega-operator",
    "path": "/execute",
}
EXPECTED_CANONICAL_IDENTITIES = ["fo-automation-agent", "fo-operator"]
EXPECTED_CANONICAL_SEQUENCE = [
    "AUTHENTICATED_STATUS",
    "READ_CLOUD_RUN_SERVICE",
    "REVERSIBLE_CANARY",
    "SEMANTIC_READBACK",
    "ROLLBACK_RECEIPT",
]
EXPECTED_CANONICAL_RECEIPTS = [
    "provider_revision",
    "request_id",
    "authenticated_principal",
    "response_status",
    "response_body_sha256",
    "readback_match",
    "rollback_receipt",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


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
    if not isinstance(stages, list):
        return {}, False
    stage_ids = [stage.get("id") for stage in stages if isinstance(stage, dict)]
    by_id = {stage.get("id"): stage for stage in stages if isinstance(stage, dict) and stage.get("id")}
    valid = stage_ids == EXPECTED_STAGE_IDS
    positions = {stage_id: index for index, stage_id in enumerate(stage_ids)}
    for stage in stages:
        if not isinstance(stage, dict):
            valid = False
            continue
        current = positions.get(stage.get("id"), -1)
        dependencies = stage.get("depends_on", [])
        if not isinstance(dependencies, list):
            valid = False
            continue
        for dependency in dependencies:
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
    authority = admission.get("provider_authority", {}) if isinstance(admission, dict) else {}
    freshness = programme.get("provider_authority_freshness", {})
    latest_verified = freshness.get("latest_verified", {}) if isinstance(freshness, dict) else {}
    github_latest = latest_verified.get("github_actions", {}) if isinstance(latest_verified, dict) else {}
    drive_latest = latest_verified.get("google_drive_document_release", {}) if isinstance(latest_verified, dict) else {}
    expansion = programme.get("live_provider_expansion", {})
    expansion_cloud = expansion.get("cloud_run_block", {}) if isinstance(expansion, dict) else {}
    canonical = programme.get("canonical_authority_reconciliation", {})
    canonical_cloud = canonical.get("cloud_run", {}) if isinstance(canonical, dict) else {}
    canonical_provider_proof = canonical.get("provider_proof", {}) if isinstance(canonical, dict) else {}

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

    canonical_route = {key: canonical_cloud.get(key) for key in EXPECTED_CANONICAL_ROUTE}
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
        "historical_live_provider_expansion_verified": (
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
        "historical_live_provider_states_precise": expansion.get("provider_states") == EXPECTED_LIVE_PROVIDER_STATES,
        "historical_cloud_run_wif_block_precise": (
            expansion_cloud.get("reason") == "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED"
            and expansion_cloud.get("previous_exact_error") == "invalid_target"
            and expansion_cloud.get("mutation_performed") is False
            and bool(expansion_cloud.get("workload_identity_provider"))
        ),
        "canonical_authority_reconciliation_verified": (
            canonical.get("status") == CANONICAL_RECONCILIATION_STATUS
            and canonical.get("manifest_id") == "FO-CLAM-2026-08-04-v1"
            and canonical.get("proof_scope") == "C03_C06_C07_C11_C14_C15_CANONICAL_PROVIDER_AUTHORITY_RECONCILIATION"
            and canonical.get("external_gate_effect") == "UNCHANGED"
            and canonical.get("owner_authority_effect") == "UNCHANGED"
            and not canonical.get("full_commercial_maturity")
            and canonical.get("receipt_file") == "alpha_omega_commercial/canonical_authority_reconciliation_receipt.json"
            and _valid_sha256(canonical.get("receipt_sha256"))
        ),
        "canonical_cloud_route_precise": canonical_route == EXPECTED_CANONICAL_ROUTE,
        "canonical_cloud_identity_and_proof_contract_precise": (
            canonical_cloud.get("candidate_identities") == EXPECTED_CANONICAL_IDENTITIES
            and canonical_cloud.get("required_sequence") == EXPECTED_CANONICAL_SEQUENCE
            and canonical_cloud.get("required_receipts") == EXPECTED_CANONICAL_RECEIPTS
            and canonical_cloud.get("provider_state") == "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
            and canonical_cloud.get("identity_authority") == "OWNER_OR_PROVIDER_CONFIGURATION_REQUIRED"
            and canonical_cloud.get("live_invocation_proven") is False
            and canonical_cloud.get("cloud_mutation_performed") is False
        ),
        "canonical_provider_proof_persisted": (
            canonical_provider_proof.get("pull_request") == 111
            and isinstance(canonical_provider_proof.get("head_sha"), str)
            and len(canonical_provider_proof.get("head_sha", "")) == 40
            and isinstance(canonical_provider_proof.get("workflow_run"), int)
            and isinstance(canonical_provider_proof.get("workflow_job"), int)
            and isinstance(canonical_provider_proof.get("artifact_id"), int)
            and canonical_provider_proof.get("artifact_name") == "alpha-omega-commercial-canonical-authority-reconciliation-proof"
            and str(canonical_provider_proof.get("artifact_digest", "")).startswith("sha256:")
            and canonical_provider_proof.get("conclusion") == "success"
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
            and authority.get("cloud_run") == "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
            and authority.get("live_cloud_operations") == "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
            and canonical_cloud.get("live_invocation_proven") is False
            and canonical_cloud.get("cloud_mutation_performed") is False
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
        "canonical_authority_reconciliation": canonical.get("status"),
        "checks": checks,
        "external_gates": maturity_gates,
        "provider_authority": authority,
        "owner_reserved_authority": sorted(EXPECTED_OWNER_RESERVED),
        "truth_boundary": (
            "This receipt proves programme-register consistency, six reversible provider operations, canonical Cloud Run route alignment, "
            "provider freshness, persistence and rollback while identity authority remains unavailable. It does not establish customer demand, "
            "a signed contract, payment-provider revenue, Cloud Run operation, enterprise attestation, partner adoption, an external case study "
            "or production-scale evidence."
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
