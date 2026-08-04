from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


PROGRAMME_ID = "AO-COMMERCIAL-MATURITY-V1"
STATUS = "EFFECTIVE_PROGRAMME_STATE_VERIFIED_C15_INSTITUTION_RECONCILED_EXTERNAL_GATES_OPEN"
CANONICAL_STATUS = "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
BASE_C15_STATUS = "COMMERCIAL_READINESS_VERIFIED_CANONICAL_PROVIDER_ROUTE_ALIGNED_EXTERNAL_MATURITY_GATES_OPEN"
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
EXPECTED_OWNER_AUTHORITY = {
    "financial_commitments": "OWNER_RESERVED",
    "contracts": "OWNER_RESERVED",
    "external_communications": "OWNER_RESERVED",
    "consequential_releases": "OWNER_RESERVED",
    "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
}
EXPECTED_PROJECTION = {
    "C11": "SERVICE_ENABLED_PLATFORM_GOVERNED_AUTHORITY_VERIFIED_SELF_SERVICE_HELD",
    "C12": "EXTERNAL_EVIDENCE_ADMISSION_AND_GOVERNED_CASE_STUDY_CONTROLS_VERIFIED_MARKET_PROOF_REQUIRED",
    "C13": "GOVERNED_REVOPS_OWNER_RECEIPT_AND_PAYMENT_ADMISSION_VERIFIED_REVENUE_PROOF_REQUIRED",
    "C15": "COMMERCIAL_READINESS_VERIFIED_INSTITUTION_RECONCILED_EXTERNAL_MATURITY_GATES_OPEN",
    "P13": "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK",
    "P15": "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
}


class EffectiveStateError(ValueError):
    """Raised when the effective commercial state cannot be admitted safely."""


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
        raise EffectiveStateError(f"{path} must contain a JSON object")
    return value


def _require(condition: bool, label: str) -> bool:
    if not condition:
        raise EffectiveStateError(label)
    return True


def _exact_dependency_order(items: Iterable[dict[str, Any]]) -> bool:
    sequence = list(items)
    expected = [f"C{index:02d}" for index in range(1, 16)]
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


def _release_hash_valid(release: dict[str, Any]) -> bool:
    candidate = dict(release)
    expected = candidate.pop("receipt_sha256", None)
    return isinstance(expected, str) and expected == digest(candidate)


def build_effective_state(
    programme: dict[str, Any],
    governed_release: dict[str, Any],
    governed_checkpoint: dict[str, Any],
    institution_checkpoint: dict[str, Any],
    institution_reconciliation: dict[str, Any],
    drive_observation: dict[str, Any],
) -> dict[str, Any]:
    stages = {item.get("id"): item for item in programme.get("stages", [])}
    programme_authority = (
        programme.get("external_evidence_admission", {})
        .get("provider_authority", {})
    )
    release_truth = governed_release.get("truth_boundary", {})
    release_gates = governed_release.get("external_gates", {})
    institution_gates = institution_reconciliation.get("external_gates", {})
    institution_truth = institution_reconciliation.get("commercial_truth", {})
    institution_proof = institution_reconciliation.get("proof", {})

    checks = {
        "programme_identity": _require(
            programme.get("programme_id") == PROGRAMME_ID,
            "commercial programme identity drift",
        ),
        "dependency_order": _require(
            _exact_dependency_order(programme.get("stages", [])),
            "C01-C15 dependency order drift",
        ),
        "canonical_status": _require(
            programme.get("canonical_status") == CANONICAL_STATUS,
            "canonical commercial status drift",
        ),
        "base_c15_lineage": _require(
            stages.get("C15", {}).get("status") == BASE_C15_STATUS,
            "base C15 lineage state drift",
        ),
        "governed_release_integrity": _require(
            governed_release.get("status")
            == governed_checkpoint.get("status")
            == "GOVERNED_COMMERCIAL_AUTHORITY_V2_RELEASE_VERIFIED_EXTERNAL_GATES_UNCHANGED"
            and _release_hash_valid(governed_release)
            and governed_checkpoint.get("release_receipt", {}).get("receipt_sha256")
            == governed_release.get("receipt_sha256"),
            "governed authority release integrity drift",
        ),
        "governed_provider_proof": _require(
            governed_release.get("provider_native_proof", {}).get("all_conclusions")
            == "success"
            and set(
                governed_release.get("provider_native_proof", {}).get(
                    "final_head_runs", {}
                )
            )
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
            "governed authority provider proof incomplete",
        ),
        "institution_reconciliation_status": _require(
            institution_reconciliation.get("status")
            == "COMMERCIAL_INSTITUTION_RECONCILIATION_PROVIDER_VERIFIED"
            and institution_reconciliation.get("programme_projection", {}).get("C15")
            == EXPECTED_PROJECTION["C15"]
            and institution_reconciliation.get("institution_projection", {}).get("P13")
            == EXPECTED_PROJECTION["P13"]
            and institution_reconciliation.get("institution_projection", {}).get("P15")
            == EXPECTED_PROJECTION["P15"],
            "institution reconciliation projection drift",
        ),
        "institution_provider_proof": _require(
            institution_proof.get("all_implementation_conclusions") == "success"
            and set(institution_proof.get("implementation_regression_runs", {}))
            == {
                "C01_C05",
                "C06_C09",
                "C10_C15",
                "provider_authority",
                "governed_authority",
                "institution_reconciliation",
                "github_control_plane",
                "superior_logic_ci",
                "repository_leak_guard",
            },
            "institution reconciliation provider proof incomplete",
        ),
        "final_pr120_proof": _require(
            drive_observation.get("pull_request") == 120
            and drive_observation.get("merge_commit")
            == "1c4ee76ecc8d93b6d4c57f57c11596db582e76cf"
            and drive_observation.get("workflow_run") == 30872211661
            and drive_observation.get("artifact_id") == 8878260625
            and drive_observation.get("artifact_digest")
            == "sha256:723fcf11265db7f038f228f1d01a25a4c44925bf043b2e7271130e0706d52b6f"
            and drive_observation.get("receipt_sha256")
            == "99f6974e21e077d8bab51fcb1d565bf1dd2f1b939947cf8933510b720b148705",
            "final PR120 provider proof drift",
        ),
        "drive_release_readback": _require(
            drive_observation.get("provider") == "GOOGLE_DRIVE"
            and drive_observation.get("file_id")
            == "1ZLPaEwlNT2BggIjum5yAg523vmvum-v4bDfXoCpwBrA"
            and drive_observation.get("readback_verified") is True
            and drive_observation.get("release_scope") == "COMMERCIAL_ONLY"
            and drive_observation.get("external_gate_effect") == "UNCHANGED",
            "Google Drive commercial release readback drift",
        ),
        "provider_scope_boundaries": _require(
            programme_authority.get("cloud_run")
            == "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
            and programme_authority.get("payment_provider")
            == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and institution_checkpoint.get("provider_authority", {}).get(
                "google_drive_write"
            )
            == "UNVERIFIED"
            and institution_checkpoint.get("provider_authority", {}).get("cloud_run")
            == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "provider scope or authority boundary drift",
        ),
        "external_gates_unchanged": _require(
            set(release_gates) == EXPECTED_EXTERNAL_GATES
            and set(institution_gates) == EXPECTED_EXTERNAL_GATES
            and all(value is False for value in release_gates.values())
            and all(value is False for value in institution_gates.values())
            and programme.get("external_gate_evidence") == {},
            "external maturity gate advanced without fresh evidence",
        ),
        "zero_revenue": _require(
            release_truth.get("verified_live_revenue_events") == 0
            and institution_truth.get("verified_live_revenue_events") == 0
            and release_truth.get("mock_provider_conformance_is_revenue") is False,
            "live revenue claimed without payment-provider evidence",
        ),
        "cloud_run_not_proven": _require(
            release_truth.get("cloud_run_operation_proven") is False
            and institution_truth.get("cloud_run_operation_proven") is False,
            "Cloud Run operation claimed without fresh provider proof",
        ),
        "full_maturity_not_claimed": _require(
            release_truth.get("full_commercial_maturity") is False
            and institution_truth.get("full_commercial_maturity") is False,
            "full commercial maturity claimed without external gates",
        ),
        "owner_authority": _require(
            governed_release.get("owner_authority") == EXPECTED_OWNER_AUTHORITY
            and institution_reconciliation.get("owner_authority")
            == EXPECTED_OWNER_AUTHORITY,
            "owner-reserved authority drift",
        ),
    }

    state: dict[str, Any] = {
        "programme_id": PROGRAMME_ID,
        "status": STATUS,
        "strategy": {
            "service_enabled_platform_first": True,
            "self_service_saas_held": True,
        },
        "base_register": {
            "canonical_status": programme.get("canonical_status"),
            "canonical_receipt_integrity": programme.get(
                "canonical_receipt_integrity"
            ),
            "base_c15_status": stages.get("C15", {}).get("status"),
        },
        "control_chain": {
            "governed_authority": {
                "pull_request": governed_checkpoint.get("implementation", {}).get(
                    "pull_request"
                ),
                "merge_commit": governed_checkpoint.get("implementation", {}).get(
                    "merge_commit"
                ),
                "release_receipt_sha256": governed_release.get("receipt_sha256"),
            },
            "governed_release_reconciliation": {
                "pull_request": institution_reconciliation.get(
                    "dependency_checkpoint", {}
                ).get("commercial_release_reconciliation_pull_request"),
                "merge_commit": institution_reconciliation.get(
                    "dependency_checkpoint", {}
                ).get("commercial_release_reconciliation_merge_commit"),
            },
            "institution_reconciliation": {
                "pull_request": drive_observation.get("pull_request"),
                "merge_commit": drive_observation.get("merge_commit"),
                "workflow_run": drive_observation.get("workflow_run"),
                "artifact_id": drive_observation.get("artifact_id"),
                "artifact_name": drive_observation.get("artifact_name"),
                "artifact_digest": drive_observation.get("artifact_digest"),
                "receipt_sha256": drive_observation.get("receipt_sha256"),
            },
            "google_drive_release": {
                "file_id": drive_observation.get("file_id"),
                "title": drive_observation.get("title"),
                "created_at": drive_observation.get("created_at"),
                "modified_at": drive_observation.get("modified_at"),
                "readback_verified": drive_observation.get("readback_verified"),
                "release_scope": drive_observation.get("release_scope"),
            },
        },
        "effective_stage_projection": dict(EXPECTED_PROJECTION),
        "provider_authority": {
            "commercial_google_drive_release": "FRESH_VERIFIED_READBACK",
            "institution_v3_google_drive_publication": "UNVERIFIED_SCOPE_HELD",
            "cloud_run": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
            "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        },
        "external_gates": dict(release_gates),
        "commercial_truth": {
            "verified_live_revenue_events": 0,
            "cloud_run_operation_proven": False,
            "full_commercial_maturity": False,
        },
        "owner_authority": dict(EXPECTED_OWNER_AUTHORITY),
        "truth_boundary": (
            "This effective-state projection reconciles the stable C01-C15 programme register with "
            "provider-verified governed-authority and institution-reconciliation receipts. It does not "
            "prove customer demand, a signed contract, payment, revenue, subscriptions, invoices, "
            "Cloud Run operation, enterprise attestation, partner adoption, an external customer case "
            "study, production scale or a v3 institution Google Drive publication."
        ),
    }
    state["state_sha256"] = digest(state)
    state["checks"] = checks
    return state
