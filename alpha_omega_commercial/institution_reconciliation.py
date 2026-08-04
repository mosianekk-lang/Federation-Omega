from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


STATUS = "COMMERCIAL_INSTITUTION_RECONCILIATION_VERIFIED_SCOPE_BOUNDARIES_PRESERVED"
COMMERCIAL_PROGRAMME_ID = "AO-COMMERCIAL-MATURITY-V1"
INSTITUTION_PROGRAMME_ID = "AO-V30-SELF-VERIFYING-INSTITUTION"
EXPECTED_OWNER_AUTHORITY = {
    "financial_commitments": "OWNER_RESERVED",
    "contracts": "OWNER_RESERVED",
    "external_communications": "OWNER_RESERVED",
    "consequential_releases": "OWNER_RESERVED",
    "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
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


class ReconciliationError(ValueError):
    """Raised when cross-programme state cannot be admitted safely."""


def digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReconciliationError(f"{path} must contain a JSON object")
    return value


def _require(condition: bool, label: str) -> bool:
    if not condition:
        raise ReconciliationError(label)
    return True


def _exact_dependency_order(items: Iterable[dict[str, Any]], prefix: str, count: int) -> bool:
    sequence = list(items)
    expected = [f"{prefix}{index:02d}" for index in range(1, count + 1)]
    actual = [item.get("id") for item in sequence]
    if actual != expected:
        return False
    seen: set[str] = set()
    for item in sequence:
        dependencies = item.get("depends_on", [])
        if not isinstance(dependencies, list) or any(dep not in seen for dep in dependencies):
            return False
        seen.add(str(item["id"]))
    return True


def verify_institution_reconciliation(
    commercial_programme: dict[str, Any],
    governed_release: dict[str, Any],
    governed_checkpoint: dict[str, Any],
    institution_programme: dict[str, Any],
    institution_checkpoint: dict[str, Any],
) -> dict[str, Any]:
    release_for_hash = dict(governed_release)
    release_hash = release_for_hash.pop("receipt_sha256", None)
    commercial_authority = (
        commercial_programme.get("external_evidence_admission", {})
        .get("provider_authority", {})
    )
    institution_authority = institution_checkpoint.get("provider_authority", {})
    truth = governed_release.get("truth_boundary", {})
    external_gates = governed_release.get("external_gates", {})
    drive_release = governed_release.get("google_drive_release", {})
    proof = governed_release.get("provider_native_proof", {})

    checks = {
        "commercial_programme_identity": _require(
            commercial_programme.get("programme_id") == COMMERCIAL_PROGRAMME_ID,
            "commercial programme identity drift",
        ),
        "institution_programme_identity": _require(
            institution_programme.get("programme_id") == INSTITUTION_PROGRAMME_ID
            and institution_checkpoint.get("programme_id") == INSTITUTION_PROGRAMME_ID,
            "institution programme identity drift",
        ),
        "commercial_dependency_order": _require(
            _exact_dependency_order(commercial_programme.get("stages", []), "C", 15),
            "commercial dependency order drift",
        ),
        "institution_dependency_order": _require(
            _exact_dependency_order(institution_programme.get("sequence", []), "P", 15),
            "institution dependency order drift",
        ),
        "canonical_status_preserved": _require(
            commercial_programme.get("canonical_status")
            == "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN",
            "commercial canonical status was promoted without external evidence",
        ),
        "governed_release_status": _require(
            governed_release.get("status")
            == governed_checkpoint.get("status")
            == "GOVERNED_COMMERCIAL_AUTHORITY_V2_RELEASE_VERIFIED_EXTERNAL_GATES_UNCHANGED",
            "governed release status mismatch",
        ),
        "release_hash_valid": _require(
            isinstance(release_hash, str)
            and release_hash == digest(release_for_hash)
            and governed_checkpoint.get("release_receipt", {}).get("receipt_sha256")
            == release_hash,
            "governed release receipt hash mismatch",
        ),
        "provider_native_runs_success": _require(
            proof.get("all_conclusions") == "success"
            and set(proof.get("final_head_runs", {}))
            == {
                "C01_C05",
                "C06_C09",
                "C10_C15",
                "provider_authority",
                "governed_authority",
                "github_control_plane",
                "superior_logic_ci",
                "repository_leak_guard",
            },
            "provider-native final-head proof is incomplete",
        ),
        "commercial_drive_release_verified": _require(
            drive_release.get("readback_verified") is True
            and drive_release.get("shared") is False
            and commercial_authority.get("google_drive_reversible_operations")
            == "FRESH_VERIFIED_OPERATIONAL",
            "commercial Drive release/readback authority is incomplete",
        ),
        "institution_drive_scope_not_inflated": _require(
            institution_authority.get("google_drive_write") == "UNVERIFIED"
            and "No v3 Google Drive publication" in institution_checkpoint.get("truth_boundary", ""),
            "commercial Drive proof was incorrectly promoted to v3 institution publication proof",
        ),
        "cloud_authority_remains_blocked": _require(
            institution_authority.get("cloud_run")
            == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and commercial_authority.get("cloud_run")
            == "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
            and truth.get("cloud_run_operation_proven") is False,
            "Cloud Run operation or authority was promoted without provider proof",
        ),
        "external_gates_unchanged": _require(
            set(external_gates) == EXPECTED_EXTERNAL_GATES
            and all(value is False for value in external_gates.values())
            and commercial_programme.get("external_gate_evidence") == {},
            "an external maturity gate was advanced without admissible evidence",
        ),
        "zero_live_revenue": _require(
            truth.get("verified_live_revenue_events") == 0
            and truth.get("mock_provider_conformance_is_revenue") is False,
            "live revenue was claimed without settled provider evidence",
        ),
        "full_maturity_not_claimed": _require(
            truth.get("full_commercial_maturity") is False,
            "full commercial maturity was claimed without all external gates",
        ),
        "owner_authority_preserved": _require(
            governed_release.get("owner_authority") == EXPECTED_OWNER_AUTHORITY,
            "owner-reserved authority drift",
        ),
    }

    blockers = [
        "MARKET_PROOF_REQUIRED:CUSTOMER_DEMAND",
        "OWNER_RESERVED:SIGNED_CUSTOMER_CONTRACT",
        "PROVIDER_BLOCKED:PAYMENT_PROVIDER_AUTHORITY",
        "PROVIDER_BLOCKED:CANONICAL_CLOUD_IDENTITY_AUTHORITY",
        "EXTERNAL_PROOF_REQUIRED:ENTERPRISE_ATTESTATION",
        "MARKET_PROOF_REQUIRED:PARTNER_ADOPTION",
        "MARKET_PROOF_REQUIRED:EXTERNAL_CUSTOMER_CASE_STUDY",
        "PRODUCTION_PROOF_REQUIRED:SCALE_AND_RECOVERY",
        "PROVIDER_WRITEBACK_REQUIRED:V30_GOOGLE_DRIVE_PUBLICATION",
    ]

    return {
        "status": STATUS,
        "programme_id": COMMERCIAL_PROGRAMME_ID,
        "institution_programme_id": INSTITUTION_PROGRAMME_ID,
        "checks": checks,
        "scope_projection": {
            "commercial_google_drive_release": "FRESH_VERIFIED_READBACK_OWNER_ONLY",
            "institution_v3_google_drive_publication": "UNVERIFIED_SCOPE_HELD",
            "commercial_service_platform": "VERIFIED",
            "self_service_saas": "HELD",
            "cloud_run_operation": "NOT_PROVEN",
        },
        "institution_projection": {
            "P13": "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK",
            "P15": "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
        },
        "commercial_projection": {
            "C15": "COMMERCIAL_READINESS_VERIFIED_INSTITUTION_RECONCILED_EXTERNAL_MATURITY_GATES_OPEN",
            "verified_live_revenue_events": 0,
            "full_commercial_maturity": False,
        },
        "blockers": blockers,
        "owner_authority": EXPECTED_OWNER_AUTHORITY,
        "source_receipts": {
            "governed_release_id": governed_release.get("release_id"),
            "governed_release_receipt_sha256": release_hash,
            "governed_release_artifact_id": proof.get("artifact_id"),
            "governed_release_artifact_digest": proof.get("artifact_digest"),
            "google_drive_release_file_id": drive_release.get("file_id"),
            "google_drive_release_exported_text_sha256": drive_release.get(
                "exported_text_sha256"
            ),
            "institution_checkpoint_id": institution_checkpoint.get("checkpoint_id"),
        },
        "truth_boundary": (
            "This reconciliation proves exact cross-programme state consistency and scope separation. "
            "It does not prove customer demand, a signed contract, payment, revenue, subscription, "
            "invoice, Cloud Run operation, enterprise attestation, partner adoption, an external "
            "customer case study, production scale, or a v3 institution Google Drive publication."
        ),
    }
