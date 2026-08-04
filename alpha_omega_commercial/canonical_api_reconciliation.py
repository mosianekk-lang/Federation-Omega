from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Type


EXPECTED_STAGE_IDS = [f"C{index:02d}" for index in range(1, 16)]
EXPECTED_OWNER_AUTHORITY = {
    "financial_commitments": "OWNER_RESERVED",
    "contracts": "OWNER_RESERVED",
    "external_communications": "OWNER_RESERVED",
    "consequential_releases": "OWNER_RESERVED",
    "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
}
EXPECTED_EXTERNAL_GATES = {
    "customer_demand_and_price_acceptance": False,
    "signed_customer_contract": False,
    "payment_provider_revenue_receipt": False,
    "live_cloud_provider_execution": False,
    "enterprise_assurance_or_certification": False,
    "partner_adoption": False,
    "external_customer_case_study": False,
    "production_scale_and_recovery_evidence": False,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def dependency_order_valid(programme: dict[str, Any]) -> bool:
    stages = programme.get("stages", [])
    if [item.get("id") for item in stages] != EXPECTED_STAGE_IDS:
        return False
    position = {stage_id: index for index, stage_id in enumerate(EXPECTED_STAGE_IDS)}
    for stage in stages:
        stage_id = stage.get("id")
        dependencies = stage.get("depends_on", [])
        if not isinstance(dependencies, list):
            return False
        for dependency in dependencies:
            if dependency not in position or position[dependency] >= position[stage_id]:
                return False
    return True


def verify_canonical_api_reconciliation(
    programme: dict[str, Any],
    compatibility_api: dict[str, Any],
    projection: dict[str, Any],
    release_checkpoint: dict[str, Any],
    institution_checkpoint: dict[str, Any],
    package_class: Type[Any],
) -> dict[str, Any]:
    effective = projection.get("effective_api", {})
    dependency = projection.get("dependency", {})
    controls = effective.get("idempotency_controls", {})
    provider = projection.get("provider_boundaries", {})
    truth = projection.get("commercial_truth", {})
    release_effective = release_checkpoint.get("effective_state", {})
    release_truth = release_checkpoint.get("commercial_truth", {})

    checks = {
        "programme_identity": programme.get("programme_id") == "AO-COMMERCIAL-MATURITY-V1",
        "programme_dependency_order": dependency_order_valid(programme),
        "compatibility_descriptor_preserved": (
            compatibility_api.get("api_id") == "AO-COMMERCIAL-CANONICAL-API-V3"
            and compatibility_api.get("capability_revision")
            == "AO-COMMERCIAL-AUTHORITY-ACTION-BINDING-V5"
            and compatibility_api.get("canonical_class")
            == "AuthoritySnapshotCommercialControlPlane"
            and compatibility_api.get("current_capability_revision")
            == "AO-COMMERCIAL-AUTHORITY-ACTION-COORDINATION-V9"
            and compatibility_api.get("current_canonical_class")
            == "CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane"
        ),
        "effective_projection_exact": (
            projection.get("projection_id")
            == "AO-COMMERCIAL-CANONICAL-API-EFFECTIVE-V10"
            and effective.get("capability_revision")
            == "AO-COMMERCIAL-AUTHORITY-ACTION-IDEMPOTENCY-V10"
            and effective.get("canonical_class")
            == "IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane"
            and effective.get("predecessor_class")
            == "CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane"
        ),
        "package_export_exact": (
            package_class.__name__
            == "IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane"
            and getattr(package_class, "CAPABILITY_REVISION", None)
            == "AO-COMMERCIAL-AUTHORITY-ACTION-IDEMPOTENCY-V10"
        ),
        "release_checkpoint_verified": (
            release_checkpoint.get("status")
            == "AUTHORITY_ACTION_IDEMPOTENCY_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED"
            and release_checkpoint.get("implementation_release", {}).get("pull_request") == 136
            and release_checkpoint.get("implementation_release", {}).get("merge_commit")
            == "31e06053764b9900f6edb8fe89a773737f1af264"
            and release_checkpoint.get("provider_proof", {}).get("checks_failed") == 0
            and release_checkpoint.get("release_reconciliation_proof", {}).get("checks_failed") == 0
        ),
        "release_effective_api_matches": (
            release_effective.get("current_capability_revision")
            == effective.get("capability_revision")
            and release_effective.get("current_supported_class")
            == effective.get("canonical_class")
            and release_effective.get("predecessor_class")
            == effective.get("predecessor_class")
        ),
        "release_drive_readback_bound": (
            dependency.get("preceding_release_pull_request") == 137
            and dependency.get("preceding_release_merge_commit")
            == "c3a1f14f2da79901c3d8e2d628f914f0beaf5a7d"
            and dependency.get("google_drive_file_id")
            == release_checkpoint.get("google_drive_release", {}).get("file_id")
            and release_checkpoint.get("google_drive_release", {}).get("readback_verified") is True
            and release_checkpoint.get("google_drive_release", {}).get("shared") is False
        ),
        "idempotency_controls_exact": controls == {
            "object_identity_is_idempotency_key": True,
            "canonical_request_intent_hash_required": True,
            "exact_retry_returns_committed_record": True,
            "exact_retry_consumes_owner_authority_again": False,
            "exact_retry_creates_new_transaction": False,
            "conflicting_object_identity_reuse_rejected": True,
            "idempotency_seal_transaction_bound": True,
            "idempotency_seal_provider_snapshot_bound": True,
            "idempotency_seal_acceptance_entry_bound": True,
            "restart_safe": True,
            "historical_unsealed_commit_replayed": False,
            "distributed_provider_exactly_once_proven": False,
        },
        "service_first_strategy_preserved": (
            projection.get("service_enabled_platform_prioritised") is True
            and projection.get("self_service_saas_held") is True
            and release_effective.get("service_enabled_platform_prioritised") is True
            and release_effective.get("self_service_saas_held") is True
        ),
        "provider_boundaries_preserved": (
            provider.get("cloud_run")
            == "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE"
            and provider.get("payment_provider")
            == "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"
            and provider.get("customer_market") == "MARKET_PROOF_REQUIRED"
            and provider.get("partner_market") == "MARKET_PROOF_REQUIRED"
            and provider.get("distributed_provider_exactly_once")
            == "PROVIDER_PROOF_REQUIRED"
        ),
        "external_gates_remain_false": (
            projection.get("external_gates") == EXPECTED_EXTERNAL_GATES
            and release_checkpoint.get("external_gates") == EXPECTED_EXTERNAL_GATES
        ),
        "commercial_truth_preserved": (
            truth.get("verified_live_revenue_events") == 0
            and truth.get("cloud_run_operation_proven") is False
            and truth.get("payment_provider_operation_proven") is False
            and truth.get("distributed_provider_exactly_once_proven") is False
            and truth.get("full_commercial_maturity") is False
            and release_truth.get("verified_live_revenue_events") == 0
            and release_truth.get("full_commercial_maturity") is False
        ),
        "institution_boundary_preserved": (
            institution_checkpoint.get("institution_projection", {}).get("P13")
            == "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK"
            and institution_checkpoint.get("institution_projection", {}).get("P15")
            == "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED"
            and institution_checkpoint.get("provider_scope", {}).get(
                "institution_v3_google_drive_publication"
            )
            == "UNVERIFIED_SCOPE_HELD"
        ),
        "owner_authority_preserved": (
            projection.get("owner_authority") == EXPECTED_OWNER_AUTHORITY
            and release_checkpoint.get("owner_authority") == EXPECTED_OWNER_AUTHORITY
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    result: dict[str, Any] = {
        "proof_id": "AO-COMMERCIAL-CANONICAL-API-EFFECTIVE-V10-PROOF",
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "status": (
            "CANONICAL_API_EFFECTIVE_V10_PROVIDER_PROOF_VERIFIED"
            if not failed
            else "CANONICAL_API_EFFECTIVE_V10_RECONCILIATION_FAILED"
        ),
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len(failed),
        "failed_checks": failed,
        "effective_capability_revision": effective.get("capability_revision"),
        "effective_canonical_class": effective.get("canonical_class"),
        "compatibility_descriptor_state": "HISTORICAL_PROVIDER_PROOF_ANCHOR_PRESERVED",
        "external_gate_effect": "UNCHANGED",
        "verified_live_revenue_events": truth.get("verified_live_revenue_events"),
        "full_commercial_maturity": truth.get("full_commercial_maturity"),
        "source_sha256": {
            "programme": digest(programme),
            "compatibility_api": digest(compatibility_api),
            "effective_projection": digest(projection),
            "release_checkpoint": digest(release_checkpoint),
            "institution_checkpoint": digest(institution_checkpoint),
        },
    }
    unsigned = copy.deepcopy(result)
    result["proof_sha256"] = digest(unsigned)
    return result


def load_and_verify(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else Path(__file__).resolve().parent
    from alpha_omega_commercial import (
        IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane,
    )

    def read(name: str) -> dict[str, Any]:
        return json.loads((base / name).read_text(encoding="utf-8"))

    return verify_canonical_api_reconciliation(
        read("programme.json"),
        read("canonical_commercial_api.json"),
        read("canonical_commercial_api_effective_v10.json"),
        read("authority_action_idempotency_release_checkpoint.json"),
        read("institution_reconciliation_checkpoint.json"),
        IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane,
    )


def require_verified(root: str | Path | None = None) -> dict[str, Any]:
    result = load_and_verify(root)
    if result["checks_failed"]:
        raise ValueError(
            "canonical API v10 reconciliation failed: "
            + ",".join(result["failed_checks"])
        )
    return result
