from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_STATUS = "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
CANONICAL_INTEGRITY_STATUS = "CANONICAL_RECEIPT_INTEGRITY_VERIFIED"
EXTERNAL_EVIDENCE_ADMISSION_STATUS = "EXTERNAL_EVIDENCE_ADMISSION_VERIFIED_GATES_UNCHANGED"
C12_STATUS = "EVIDENCE_FRAMEWORK_AND_EXTERNAL_ADMISSION_VERIFIED_MARKET_PROOF_REQUIRED"
C13_STATUS = (
    "REFERENCE_REVOPS_AND_PAYMENT_EVIDENCE_ADMISSION_VERIFIED_"
    "OWNER_APPROVAL_AND_REVENUE_PROOF_REQUIRED"
)
C15_STATUS = (
    "COMMERCIAL_READINESS_VERIFIED_CANONICAL_RECEIPT_INTEGRITY_VERIFIED_"
    "EXTERNAL_EVIDENCE_ADMISSION_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
)

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
    "cloud_run": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    "customer_market": "MARKET_PROOF_REQUIRED",
    "partner_market": "MARKET_PROOF_REQUIRED",
    "external_attestation": "UNVERIFIED",
    "live_cloud_operations": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _stage_index(programme: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], bool]:
    stages = programme.get("stages", [])
    stage_ids = [stage.get("id") for stage in stages]
    by_id = {stage.get("id"): stage for stage in stages if stage.get("id")}
    dependency_order_valid = stage_ids == EXPECTED_STAGE_IDS
    positions = {stage_id: index for index, stage_id in enumerate(stage_ids)}
    for stage in stages:
        current = positions.get(stage.get("id"), -1)
        for dependency in stage.get("depends_on", []):
            if dependency not in positions or positions[dependency] >= current:
                dependency_order_valid = False
    return by_id, dependency_order_valid


def verify_programme_register(
    programme: dict[str, Any],
    integrity: dict[str, Any],
    maturity: dict[str, Any],
    commercial_receipt: dict[str, Any],
) -> dict[str, Any]:
    stages, dependency_order_valid = _stage_index(programme)
    c11 = stages.get("C11", {})
    c12 = stages.get("C12", {})
    c13 = stages.get("C13", {})
    c15 = stages.get("C15", {})
    maturity_gates = maturity.get("external_gates", {})
    declared_gate_labels = set(programme.get("external_maturity_gates", []))
    declared_evidence = programme.get("external_gate_evidence", {})
    admission = programme.get("external_evidence_admission", {})
    authority = admission.get("provider_authority", {})

    gate_evidence_valid = True
    for label, key in EXTERNAL_GATE_LABELS.items():
        achieved = bool(maturity_gates.get(key))
        evidence = declared_evidence.get(key)
        if achieved and not evidence:
            gate_evidence_valid = False
        if not achieved and evidence:
            gate_evidence_valid = False

    canonical_reference = programme.get("canonical_receipt", {})
    receipt_integrity = commercial_receipt.get("canonical_receipt_integrity", {})
    c13_proof = commercial_receipt.get("stages", {}).get("C13", {}).get("proof", {})

    checks = {
        "programme_identity": programme.get("programme_id") == "AO-COMMERCIAL-MATURITY-V1",
        "service_enabled_priority_preserved": (
            "service-enabled platform" in programme.get("objective", "").lower()
            and "SERVICE_ENABLED_REFERENCE_PLATFORM_VERIFIED" in c11.get("status", "")
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
        "c12_admission_status_verified": c12.get("status") == C12_STATUS,
        "c13_admission_status_verified": c13.get("status") == C13_STATUS,
        "c15_register_status_verified": c15.get("status") == C15_STATUS,
        "integrity_checks_pass": bool(integrity.get("checks")) and all(integrity.get("checks", {}).values()),
        "technical_reference_ready": bool(maturity.get("technical_reference_ready")),
        "full_commercial_maturity_not_claimed": not bool(maturity.get("full_commercial_maturity")),
        "external_gate_labels_complete": declared_gate_labels == set(EXTERNAL_GATE_LABELS),
        "external_gate_values_complete": set(maturity_gates) == set(EXTERNAL_GATE_LABELS.values()),
        "external_gate_evidence_consistent": gate_evidence_valid,
        "owner_reserved_authority_preserved": set(programme.get("owner_reserved_authority", [])) == EXPECTED_OWNER_RESERVED,
        "zero_revenue_preserved": c13_proof.get("verified_revenue_events") == 0,
        "cloud_run_not_claimed": commercial_receipt.get("truth_boundaries", {}).get("cloud_run") == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        "canonical_artifact_reference_matches": (
            canonical_reference.get("pull_request") == 93
            and canonical_reference.get("merge_commit") == "a897cb4788da76f11702b12dc0c5ed06c8b9acfa"
            and canonical_reference.get("workflow_run") == 30835362760
            and canonical_reference.get("artifact_id") == 8864581266
            and canonical_reference.get("artifact_digest")
            == "sha256:f011a0c70c979de6a714bef5d582c4d0c9c96e8cda9879fc09154195e5b1725d"
            and canonical_reference.get("integrity_receipt_sha256")
            == "1908449a171078d4592199cddabdc8187df2d2069776df838a0b027e56f6a7e0"
            and canonical_reference.get("google_drive_release_file_id")
            == "1L4ysPqtf8x2c9E-3dwVi4KDt5QwR53Oc4suFZXqSe2Q"
        ),
    }

    result = {
        "status": "PROGRAMME_REGISTER_INTEGRITY_VERIFIED" if all(checks.values()) else "PROGRAMME_REGISTER_INTEGRITY_FAILED",
        "verified_at": utc_now(),
        "programme_id": programme.get("programme_id"),
        "canonical_status": programme.get("canonical_status"),
        "canonical_receipt_integrity": programme.get("canonical_receipt_integrity"),
        "external_evidence_admission": admission.get("status"),
        "checks": checks,
        "external_gates": maturity_gates,
        "provider_authority": authority,
        "owner_reserved_authority": sorted(EXPECTED_OWNER_RESERVED),
        "truth_boundary": (
            "This receipt proves machine-readable programme-register consistency, exact provider-authority scope and "
            "fail-closed external-evidence admission readiness. It does not establish customer demand, a signed contract, "
            "payment-provider revenue, Cloud Run operation, enterprise attestation, partner adoption, an external case "
            "study or production-scale evidence."
        ),
    }
    result["receipt_sha256"] = digest(result)
    return result


def verify_from_paths(
    programme_path: str | Path,
    artifact_root: str | Path,
) -> dict[str, Any]:
    root = Path(artifact_root)
    return verify_programme_register(
        read_json(programme_path),
        read_json(root / "canonical-receipt-integrity.json"),
        read_json(root / "commercial-maturity.json"),
        read_json(root / "commercial-c10-c15-receipt.json"),
    )
